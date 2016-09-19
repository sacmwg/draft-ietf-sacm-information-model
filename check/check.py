#!/usr/bin/env python

import lxml.etree
import optparse
import sys
import os
import re

class ListToken:
    def __init__(self, name):
        self.element = name
        self.cardinality = None
        self.minimum = None
        self.maximum = None
        self.next = None

    def toString(self):
        v = "<a href='#node__" + self.element + "'>" + self.element + "</a>"
        if self.cardinality:
            v += self.cardinality
        if self.next:
            if self.next == "|":
                v += " "
            v += self.next
        return v

    
class enumValue:
    def __init__(self, line):
        line = line.strip()
        values = line.split(";")
        if len(values) != 3:
            print("Error Line: '" + line + "'", file=sys.stderr)
            raise SyntaxError("Incorrect number of fields in enumeration")
        
        x = re.match("^[0-9a-zA-Z_]+$", values[0].strip())
        if not x:
            print("Error Line: '" + line + "'", file=sys.stderr)
            raise SyntaxError("Name does not match pattern")
        self.name = values[0].strip()
        
        x = re.match("^0x([0-9a-fA-F]+)$", values[1].strip())
        if not x:
           print("Error Line: '" + line + "'", file=sys.stderr)
           raise SyntaxError("Value is not a hexadecimal number")
        self.tag = values[1].strip()
        self.value = int(values[1].strip(), 16)

        x = re.match("^[0-9a-zA-Z\.,_ ]+$", values[2].strip())
        if not x:
            print("Error Line: '" + line + "'", file=sys.stderr)
            print("Description does not match pattern", file=sys.stderr)
        self.description = values[2].strip()
        
class IPFIX:
    def __init__(self, node):
        lastItem = None

        self.id = None
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

        this = None

        if node.attrib["type"] != "IPFIX":
            raise SyntaxError("Not an IPFIX node")
        rg = node.text.split("\n")

        for line in rg:
            last = this
            this = None
            line = line.strip()
            x = re.match("elementId:\s+(\w+)\s*$", line)
            if x:
                if self.id:
                    raise SyntaxError("Duplicate elementId field");
                self.id = x.group(1)
                continue
    
            x = re.match("name:\s+([\w-]+)\s*$", line)
            if x:
                if self.name:
                    raise SyntaxError("Duplicate name field")
                self.name = x.group(1)
                continue

            x = re.match("dataType:\s+(\w+)", line);
            if x:
                if self.dataType:
                    raise SyntaxError("Duplicate dataType field")
                self.dataType = x.group(1)
                continue

            x = re.match("dataTypeSemantics:\s+(\w+)", line);
            if x:
                if self.dataTypeStatus:
                    raise SyntaxError("Duplicate dataTypeSemantics");
                self.dataTypeStatus = x.group(1)
                continue

            x = re.match("status:\s+(\w+)", line);
            if x:
                if self.status:
                    raise SyntaxError("duplicate status field")
                self.status = x.group(1)
                continue

            x = re.match("description:\s+(.+)", line);
            if x:
                if self.description:
                    raise SyntaxError("Duplicate description field");
                this = "description"
                self.description = x.group(1);
                continue

            x = re.match("description:", line);
            if x:
                this = "description"
                self.description = ""
                continue

            x = re.match("range:\s+(\w+)", line)
            if x:
                if self.range:
                    raise SyntaxError("Duplicate range field")
                self.range = x.group(1)
                continue

            x = re.match("units:\s+(\w+)", line)
            if x:
                if self.units:
                    raise SyntaxError("Duplicate units field")
                self.units = x.group(1)
                continue

            x = re.match("references:\s*(\w+)", line)
            if x:
                if self.references:
                    raise SyntaxError("Duplicate references field")
                self.references = x.group(1)
                continue

            x = re.match("structure:(.*)", line)
            if x:
                if self.structure:
                    raise SyntaxError("Duplicate structure field")
                this = "structure"
                try:
                    self.structure = x.group(1)
                except IndexError as e:
                    self.structure = ""
                continue
            
            x = re.match("structure:", line)
            if x:
                last = "structure"
                continue

            if last == "description":
                t = line.lstrip()
                if t =="":
                    self.description += "\n"
                else:
                    self.description += " "
                self.description += line.lstrip()
                this = last
                
            if last == "structure":
                t = line.lstrip()
                self.structure += "\n"
                self.structure += line.lstrip()
                this = last
                
        if (self.description == None):
            raise SyntaxError("description is a required elment")
        while (self.description[-1:] == '\n'):
            self.description = self.description[:-1]

        if not self.id:
            raise SyntaxError("elementID is a required element")
        if not self.name:
            raise SyntaxError("name is a required element")
        if not self.dataType:
            raise SyntaxError("dataType is a required element")

        if self.dataType == "enumeration":
            if not self.structure:
                raise SyntaxError("Structure field is missing for enumeration")
            self.processEnumeration(node)

        if self.dataType == "orderedList":
            if not self.structure:
                raise SyntaxError("Structure field is missing for orderedList")
            self.processOrderedList(node)

        if self.dataType == "list":
            if not self.structure:
                raise SyntaxError("Structure field is missing for list")
            self.processList(node)
            
    def processEnumLine(self, line, node):
        if line.strip() == "":
            return
        try:
            item = enumValue(line)
            if item.name in self.enums:
                print("Error: name '" + item.name + "' defined twice in enumeration", file=sys.stderr)
            else:
                self.enums[item.name] = item
                if item.value in self.enumByValue:
                    print("Error: value '" + format(item.value, "#x") + "' defined twice in enumeration", file=sys.stderr)
            return item
        except SyntaxError as e:
            print("Error at line " + str(node.sourceline) + ": " + e.msg, file=sys.stderr)

    def processEnumeration(self, node):
        enums = self.structure.split("\n")
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

    # Run the state machine for
    # rule = '(' node ( ("|" | ",") node ) ')'
    # node = name ( "*" | "+" | "?" | "(" int ("," int)? ")" )
    def buildListTokens(self, node, tokens):
        state = "rule"
        newToken = None
        token = None
        tokenIndex = 0
        self.tokenList = []
        if tokens[-1] == "":
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

    optionparser = optparse.OptionParser(usage='check SOURCE [OPTOINS] ', formatter=formatter)

    plain_options = optparse.OptionGroup(optionparser, 'Plain Options')
    plain_options.add_option('-q', '--quiet', action='store_true',
                             dest='quite', help='dont print anything')
    plain_options.add_option('-5', '--html', action='store_true',
                             dest='html', help='Output HTML format')
    plain_options.add_option('-A', '--asn', action='store_true',
                             dest='asn', help='Output ASN.1 format')
    plain_options.add_option('-o', '--output', help='file to print to',
                             dest='output', action='store')
                             
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

    # Parse the document into an xml tree instance
    parser = lxml.etree.XMLParser(dtd_validation=False,
                                  load_dtd=False, attribute_defaults=False,
                                  no_network=True, remove_comments=True,
                                  remove_pis=True, remove_blank_text=True,
                                  resolve_entities=False, strip_cdata=True)
     
    tree = lxml.etree.parse(source, parser)

    all = {"unsigned8":None, "unsigned16": None, "unsigned32":None, "unsigned64":None,
           "signed8":None, "signed16":None, "signed32":None, "signed64":None,
           "float32":None, "float64":None, "boolean":None, "macAddress":None,
           "string":None, "dateTimeSeconds":None, "dateTimeMilliseconds":None,
           "dateTimeNanoseconds":None, "ipv4Address":None, "ipv6Address":None,
           "octetArray":None, "list":None, "orderedList":None, "enumeration":None
    }
    
    for element in tree.getroot().iter():
        if element.tag == "artwork" and "type" in element.attrib:
            try:
                node = IPFIX(element)
                if node.name in all:
                    print("Error: name '" + node.name + "' defined twice", file=sys.stderr)
                else:
                    all[node.name] = node
            except SyntaxError as e:
                print("Error at line " + str(element.sourceline) + ": " + e.msg, file=sys.stderr)
    
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

    for k,v in all.items():
        if v != None:
            if options.html:
                print("<tr id='node__" + v.name + "'>", file=fout)
                print("<td>" + v.name + "</td>", file=fout)
                print("<td>" + v.dataType + "</td>", file=fout)
                print("<td>" + v.description.replace("\n", "<br><br>"), file=fout)
                if v.enumeration:
                    print("<table>", file=fout)
                    for ve in v.enumeration:
                        print("<tr><td>" + ve.name + "</td><td>" + ve.tag + "</td><td>" + ve.description + "</td></tr>", file=fout)
                    print("</table>", file=fout)
                if (v.dataType == "list" or v.dataType == "orderedList") and (v.tokenList != None):
                    print("<br>" + v.dataType + "(", file=fout)
                    for token in v.tokenList:
                        print(token.toString(), file=fout)
                    print(")", file=fout)
                print("</td>", file=fout)
            elif options.asn:
                print("", file=fout)
                #if v.description:
                #    print("-- " + v.description);
                print(v.name + " ::= " + v.dataType, file=fout)
    
    if options.html:
        print("</tbody>", file=fout)
        print("</body>", file=fout)

def CopyFile(fileName, fileOut):
    fin = open(fileName,"r");
    lines = fin.readlines()
    for line in lines:
        print(line, file=fileOut)
    fin.close()
    

def PrintError(node, text):
    if node == None:
        print("Error: " + text, file=sys.stderr)
    else:
        print("Error at line " + str(node.sourceline) + ": " + text, file=sys.stderr)

if __name__ == '__main__':
    main()
