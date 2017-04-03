#!/usr/bin/env python

import optparse
import sys
import os
import re
import csv
import textwrap

class ListToken:
    def __init__(self, name):
        self.element = name
        self.cardinality = None
        self.minimum = None
        self.maximum = None
        self.next = None

    def toString(self, reference):
        if reference:
            v = "<a href='#node__" + self.element + "'>"
        else:
            v = ""
        v += self.element
        if reference:
            v += "</a>"
        if self.cardinality:
            v += self.cardinality
        if self.next:
            if self.next == "|":
                v += " "
            v += self.next
        return v

    
class enumValue:
    def __init__(self, node, line):
        line = line.strip()
        values = line.split(";")
        self.value = None
        self.tag = None
        self.description = None
        
        if len(values) != 3:
            PrintError(node, "Incorrect number of fields for enumeration.\nLine is '" + line + "'")

        if len(values) == 0:
            return None
        x = re.match("^[0-9a-zA-Z_]+$", values[0].strip())
        if not x:
            PrintError(node, "Enumeration name does not match pattern\nLine is '" + line + "'")
        self.name = values[0].strip()

        if len(values) > 1:
            x = re.match("^0x([0-9a-fA-F]+)$", values[1].strip())
            if not x:
                PrintError(node, "Enumeration value is not a hexadecimal number\nLine is '" + line + "'")
            else:
                self.value = int(values[1].strip(), 16)
            self.tag = values[1].strip()

        if len(values) > 2:
            x = re.match("^[0-9a-zA-Z\.,_ ]+$", values[2].strip())
            if not x:
                PrintError(node, "Enumeration description does not match pattern\nLine is '" + line + "'")
            self.description = values[2].strip()
        

class IPFIX:
    def __init__(self, row):
        lastItem = None

        self.id = None
        self.enterpriseId = None
        self.name=None
        self.dataType = None
        self.description = None
        self.dataTypeStatus = None
        self.status = None
        self.range = None
        self.units = None
        self.references = None
        self.structure = None
        self.enumeration = None
        self.tokenList = None

        this = None

        self.enterpriseId = row["enterpriseId"]
        self.status = row["status"]
        self.structure = row["structure"]
                
        self.description = row["description"]
        if (self.description == ''):
            PrintError(row, "description is a required elment")
            self.description = "MISSING"

        self.id = row["elementId"]
        if self.id == '':
            PrintError(row, "elementID is a required element")
            self.elementID = "TBD"
        
        self.name = row["name"]
        if self.name == '':
            raise SyntaxError("name is a required element")
        
        self.references = row["references"]
        if self.references == '':
           self.references = None 

        self.dataType = row["dataType"]
        if self.dataType == '':
            PrintError(row, "dataType is a required element")
            self.dataType = "Unknown"

        elif self.dataType == "enumeration":
            if not self.structure:
                PrintError(row, "Structure field is missing for enumeration")
            else:
                self.processEnumeration(row)

        elif self.dataType == "orderedList":
            if not self.structure:
                PrintError(row, "Structure field is missing for orderedList")
            else:
                self.processOrderedList(row)

        elif self.dataType == "list":
            if not self.structure:
                PrintError(row, "Structure field is missing for list")
            else:
                self.processList(row)

        elif self.dataType == "category":
            if not self.structure:
                PrintError(row,"Structure field is missing for category")
            else:
                self.processCategory(row)

                
    def processEnumLine(self, line, node):
        if line.strip() == "":
            return
        try:
            item = enumValue(node, line)
            if item != None:
                if item.name in self.enums:
                    PrintError(node, "Enumeration name '" + item.name + "' defined twice in enumeration")
                else:
                    self.enums[item.name] = item
                    if item.value != None and item.value in self.enumByValue:
                        PrintError(node, "Value '" + format(item.value, "#x") + "' defined twice in enumeration", file=sys.stderr)
            return item
        except SyntaxError as e:
            PrintError(node, e.msg)

    def processEnumeration(self, node):
        enums = self.structure.split("||")
        newList = []
        lastLine = ""
        self.enums = {}
        self.enumByValue = {}
        for line in enums:
            if re.search(";", line):
                x = self.processEnumLine(lastLine, node)
                if x:
                    newList.append(x)
                lastLine = ""
            lastLine += " " + line

        x = self.processEnumLine(lastLine, node)
        if x:
            newList.append(x)
        self.enumeration = newList

    def processOrderedList(self, node):
        fullLine = self.structure.split("\n");
        fullLine = " ".join(fullLine)
        fullLine = fullLine.strip()
        # print("OrderedList: '" + fullLine + "'", file=sys.stderr)
        tokens = re.split("([\(\)\+,?|])", fullLine)
        if tokens[0].strip() != "orderedList":
            PrintError(node, "OrderedList element does not have list structure " + tokens[0])
        self.buildListTokens(node, tokens[1:])

    def processList(self, node):
        fullLine = self.structure.split("\n");
        fullLine = " ".join(fullLine)
        fullLine = fullLine.strip()
        # print("List: '" + fullLine + "'", file=sys.stderr)
        tokens = re.split("([\(\)\+,?|])", fullLine)
        if tokens[0].strip() != "list":
            PrintError(node, "List element does not have list structure " + tokens[0])
        self.buildListTokens(node, tokens[1:])

    def processCategory(self, node):
        fullLine = self.structure.split("\n");
        fullLine = " ".join(fullLine)
        fullLine= fullLine.strip()
        tokens = re.split("([\(\)|])", fullLine);
        if tokens[0].strip() != "category":
            PrintError(node, "Category element does not have list structure " + tokens[0])
        self.buildListTokens(node,tokens[1:])

    # Run the state machine for
    # rule = '(' node ( ("|" | ",") node ) ')'
    # node = name ( "*" | "+" | "?" | "(" int ("," int)? ")" )
    def buildListTokens(self, node, tokens):
        state = "rule"
        newToken = None
        token = None
        tokenIndex = 0
        self.tokenList = []
        if len(tokens) > 0 and tokens[-1] == "":
            tokens = tokens[:-1]
        while True:
            if token == None:
                while True:
                    if tokenIndex == len(tokens):
                        if state != "end":
                            PrintError(node, "Badly formatted list")
                        return
                    token = tokens[tokenIndex].strip()
                    tokenIndex += 1
                    if token != "":
                        break;
                
            
            # print("Token: " + state + "  '" + token + "'", file=sys.stderr)
            if state == "rule":
                if token != '(':
                    PrintError(node, "Expected token '(', found token " + token)
                    return
                else:
                    state = "node"
                    token = None
            elif state == "node":
                if not re.match("^\w+$", token):
                    PrintError(node, "Expected ie-name, found token " + token)
                    return
                else:
                    newToken = ListToken(token)
                    self.tokenList.append(newToken)
                    state = "cardinality"
                    token = None
            elif state == "cardinality":
                if token == "*" or token == "+" or token == "?":
                    newToken.cardinality = token
                    state = "next"
                    token = None
                elif token == "(":
                    newToken.cardiality = ","
                    state = "minimum"
                    token = None
                elif token == "|" or token == "," or token == ")":
                    state = "next"
                else:
                    PrintError(node, "Expected sperator token, found token " + token)
                    return
            elif state == "minimum":
                if not re.match("^\d+$", token):
                    PrintError(node, "Expected number, found token " + token)
                    return
                else:
                    newToken.minimum = token
                    token = None
                    state = "comma"
            elif state == "comma":
                if token == "|" or token == "," or token == ")":
                    state = "next"
                elif token == ",":
                    state = "max"
                    token = None
                else:
                    PrintError(node, "Expected comma, found token " + token)
                    return
            elif state == "max":
                if not re.match("^\d+$", token):
                    PrintError(node, "Expected number, found token " + token)
                    return
                else:
                    newToken.maximum = token
                    token = None
                    state = "close"
            elif state == "close":
                if token == ")":
                    token = None
                    state = "next"
                else:
                    PrintError(node, "Expected ')', found token " + token)
            elif state == "next":
                if token == ',' or token == '|':
                    newToken.next = token
                    token = None
                    state = "node"
                elif token == ')':
                    state = "end"
                    token = None
                else:
                    PrintError(node, "Expected ',', '|' or ')', found token " + token)
                    return
            else:
                PrintError(node, "Internal Error")
                return
                
                
def main():
    formatter = optparse.IndentedHelpFormatter(max_help_position=40)

    optionparser = optparse.OptionParser(usage='generate SOURCE [OPTOINS] ', formatter=formatter)

    column1 = 20
    column2 = 55

    plain_options = optparse.OptionGroup(optionparser, 'Plain Options')
    plain_options.add_option('-q', '--quiet', action='store_true',
                             dest='quite', help='dont print anything')
    plain_options.add_option('-o', '--output', help='file to print to',
                             dest='output', action='store')
    plain_options.add_option("-X", '--xml', action='store_true',
                             dest='xml', help='generate xml2rfc output')
    plain_options.add_option("-H", '--html', action='store_true',
                             dest='html', help='generate html output')
    plain_options.add_option('-A', '--asn', action='store_true',
                             dest='asn', help='Output ASN.1 format')
    plain_options.add_option('-l', '--left', help="column to start text in",
                             dest="column1", action='store', default=13, type="int")
    plain_options.add_option('-r', '--right', help="right most column",
                             dest="column2", action='store', default=60, type="int")

    optionparser.add_option_group(plain_options)

    (options, args) = optionparser.parse_args()
    if len(args) < 1:
        optionparser.print_help()
        sys.exit(2)

    source = args[0]
    if not os.path.exists(source):
        sys.exit('No source file: ' + source)

    fout = sys.stdout
    if options.output != None:
        fout = open(options.output, "w");

    column1 = options.column1
    column2 = options.column2
        
    fout = sys.stdout
    if options.output != None:
        fout = open(options.output, "w")

    all = {"unsigned8":None, "unsigned16": None, "unsigned32":None, "unsigned64":None,
           "signed8":None, "signed16":None, "signed32":None, "signed64":None,
           "float32":None, "float64":None, "boolean":None, "macAddress":None,
           "string":None, "dateTimeSeconds":None, "dateTimeMilliseconds":None,
           "dateTimeNanoseconds":None, "ipv4Address":None, "ipv6Address":None,
           "octetArray":None, "list":None, "orderedList":None, "enumeration":None
    }

    asn1 = {"octetArray":"OCTET STRING", "string":"UTF8String",
            "unsigned8":"INTEGER", "unsigned16":"INTEGER", "unsigned32":"INTEGER", "unsigned64":"INTEGER",
            "signed8":"INTEGER", "signed16":"INTEGER", "signed32":"INTEGER", "signed64":"INTEGER",
            "float32":"FLOAT", "float64":"FLOAT",
            "boolean":"BOOLEAN"
            }

    # Parse the document as a CSV file

    with open(source) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                node = IPFIX(row)
                if node.name in all:
                    print("Error: name '" + node.name + "' defined twice", file=sys.stderr)
                else:
                    all[node.name] = node
            except SyntaxError as e:
                print("Error a line " + csvfile.sourceline)

    print("Parse file done")
                
    for k, v in all.items():
        if v != None:
            if v.dataType not in all:
                PrintError(None, k + " dataType '" + v.dataType + "' not defined")
            if (v.dataType == "list" or v.dataType == "orderedList") and (v.tokenList != None):
                for token in v.tokenList:
                    if token.element not in all:
                        PrintError(None, "List item '" + token.element + "' not defined")

    if options.html:
        print("<!DOCTYPE html PUBLIC '-//W3C/DTD XHTML 1.0 Transitional//EN' 'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'>", file=fout)
        print("<html xmlns='http://www.w3.org/1999/xhtml' xml:lang='en-us'>", file=fout)
        print("<head>", file=fout)
        print("<title>SACM Information Model</title>", file=fout)
        
        print("<script type='text/javascript'>", file=fout)
        CopyFile('css/jquery.js', fout)
        print("</script>", file=fout)
        
        print("<script type='text/javascript'>", file=fout)
        CopyFile('css/tablesorter.min.js', fout)
        print("</script>", file=fout)
        
        print("<script type='text/javascript'>", file=fout)
        print("$(document).ready(function(){ $('#myTable').tablesorter();});", file=fout)
        print("</script>", file=fout)
        
        # print("<style>", file=fout)
        # CopyFile('css/jq.css', fout)
        # print("</script>", file=fout)
        
        print("<style>", file=fout)
        CopyFile('css/style.css', fout)
        print("</style>", file=fout)
        
        print("</head>", file=fout)
        print("<body>", file=fout)
        print("<table id='myTable' class='tablesorter'>", file=fout)
        print("<thead>", file=fout)
        print("<tr><th>Name</th><th>Type</th><th>Description</th></tr>", file=fout)
        print("<tbody>", file=fout)


    for k in sorted(all.keys()):
        v = all[k]
        if v != None:
            if options.html:
                print("<tr id='node__" + v.name + "'>", file=fout)
                print("<td>" + v.name + "</td>", file=fout)
                print("<td>" + v.dataType + "</td>", file=fout)
                print("<td>" + v.description.replace("\n", "<br><br>"), file=fout)
                if v.enumeration:
                    print("<table>", file=fout)
                    for ve in v.enumeration:
                        print("<tr><td>" + ve.name + "</td><td>", file=fout)
                        if ve.tag == None:
                            print("NONE", file=fout)
                        else:
                            print(ve.tag, file=fout)
                            print("</td><td>", file=fout)
                            if ve.description != None:
                                print(ve.description, file=fout)
                                print("</td></tr>", file=fout)
                                print("</table>", file=fout)
                if (v.dataType == "list" or v.dataType == "orderedList" or v.dataType == "category") and (v.tokenList != None):
                    print("<br>" + v.dataType + "(", file=fout)
                for token in v.tokenList:
                    print(token.toString(True), file=fout)
                    print(")", file=fout)
                print("</td>", file=fout)
            elif options.xml:
                print("<section title='" + v.name + "'>", file=fout)
                print("<figure>", file=fout)
                print("<artwork type='IPFIX'>", file=fout)
                PrintItem("elementId", v.id, column1, column2, fout)
                PrintItem("name", v.name, column1, column2, fout)
                PrintItem("dataType", v.dataType, column1, column2, fout)
                PrintItem("status",  v.status, column1, column2, fout)
                PrintItem("description",  v.description, column1, column2, fout)
                if v.enumeration:
                    label = "structure"
                    for ve in v.enumeration:
                        if ve.tag == None:
                            tag = "NONE"
                        else:
                            tag = ve.tag
                        PrintItem(label, ve.name + "; " + tag + "; " + ve.description, column1, column2, fout)
                        label = None
                if (v.dataType == "list" or v.dataType == "orderedList" or v.dataType == "category") and (v.tokenList != None):
                    tokens = v.dataType + "("
                    for token in v.tokenList:
                        tokens = tokens + token.toString(False) + " "
                    tokens = tokens + ")"
                    PrintItem("structure", tokens, column1, column2, fout)
                if v.references != None:
                    PrintItem("references", v.references, column1, column2, fout)
                print("</artwork>", file=fout)
                print("</figure>", file=fout)
                print("</section>", file=fout)
            elif options.asn:
                if not v.dataType in asn1:
                    print("", file=fout)
                    if v.enumeration:
                        ASN_EmitEnumeration(v, fout)
                    elif v.tokenList:
                        ASN_EmitTokenList(v, fout)
                    else:
                        #if v.description:
                        #    print("-- " + v.description);
                        print("X_" + v.name + " ::= " + v.dataType, file=fout)
    
    if options.html:
        print("</tbody>", file=fout)
        print("</body>", file=fout)


def PrintError(node, text):
    if node == None:
        print("Error: {0}".format(text), file=sys.stderr)
    elif type(node) is int:
        print("Error at line {0!s}: {1}".format(node, text), file=sys.stderr)
    elif type(node) is str:
        print("Error at line {0}: {1}".format(node, text), file=sys.stderr)
    else:
        print("Error at line {0!s}: {1}".format(node['name'], text), file=sys.stderr)


def PrintItem(label, value, column1, column2, fout):
    foo = "{:<" + str(column1) + "}"
    if label == None:
        value = foo.format(" ") + value
    elif len(label) + 1 > column1:
        value = (label + ": ") + value
    else:
        value = foo.format(label + ":") + value

    rows = value.split('\n')

    wrapper = textwrap.TextWrapper()
    wrapper.break_long_words = False
    wrapper.width = column2
    wrapper.subsequent_indent = ' '*column1
    
    for line in rows:
        if len(line) > column2:
            print ("\n".join(wrapper.wrap(line)), file=fout)
        else:
            print (line, file=fout)
        
def CopyFile(fileName, fileOut):
    fin = open(fileName,"r");
    lines = fin.readlines()
    for line in lines:
        print(line, file=fileOut)
    fin.close()
    
        
        
        
if __name__ == '__main__':
    main()
