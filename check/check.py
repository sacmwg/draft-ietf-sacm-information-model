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
    def __init__(self, node):
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
                    PrintError(node, "Duplicate elementId field");
                self.id = x.group(1)
                continue
    
            x = re.match("enterpriseId:\s+(\w+)\s*$", line)
            if x:
                if self.enterpiseId:
                    PrintError(node, "Duplicate enterpriseId field");
                self.enterpriseId = x.group(1)
                continue
    
            x = re.match("name:\s+([\w-]+)\s*$", line)
            if x:
                if self.name:
                    PrintError(node, "Duplicate name field")
                self.name = x.group(1)
                continue

            x = re.match("dataType:\s+(\w+)", line);
            if x:
                if self.dataType:
                    PrintError(node, "Duplicate dataType field")
                self.dataType = x.group(1)
                continue

            x = re.match("status:\s+(\w+)", line);
            if x:
                if self.status:
                    PrintError(node, "Duplicate status field")
                self.status = x.group(1)
                continue

            x = re.match("description:\s+(.+)", line);
            if x:
                if self.description:
                    PrintError(node, "Duplicate description field");
                this = "description"
                self.description = x.group(1);
                continue

            x = re.match("description:", line);
            if x:
                this = "description"
                self.description = ""
                continue

            x = re.match("structure:(.*)", line)
            if x:
                if self.structure:
                    PrintError(node, "Duplicate structure field")
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

            x = re.match("references:\s*(\w+)", line)
            if x:
                if self.references:
                    PrintError(node, "Duplicate references field")
                self.references = x.group(1)
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
            PrintError(node, "description is a required elment")
            self.description = "MISSING"
        while (self.description[-1:] == '\n'):
            self.description = self.description[:-1]

        if not self.id:
            raise SyntaxError("elementID is a required element")
        if not self.name:
            raise SyntaxError("name is a required element")
        if not self.dataType:
            PrintError(node, "dataType is a required element")
            self.dataType = "Unknown"

        if self.dataType == "enumeration":
            if not self.structure:
                PrintError(node, "Structure field is missing for enumeration")
            else:
                self.processEnumeration(node)

        if self.dataType == "orderedList":
            if not self.structure:
                PrintError(node, "Structure field is missing for orderedList")
            else:
                self.processOrderedList(node)

        if self.dataType == "list":
            if not self.structure:
                PrintError(node, "Structure field is missing for list")
            else:
                self.processList(node)
            
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

    optionparser = optparse.OptionParser(usage='check SOURCE [OPTOINS] ', formatter=formatter)

    plain_options = optparse.OptionGroup(optionparser, 'Plain Options')
    plain_options.add_option('-q', '--quiet', action='store_true',
                             dest='quite', help='dont print anything')
    plain_options.add_option('-5', '--html', action='store_true',
                             dest='html', help='Output HTML format')
    plain_options.add_option('-C', '--csv', action='store_true',
                             dest='csv', help='Output CSV format')
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

    asn1 = {"octetArray":"OCTET STRING", "string":"UTF8String",
            "unsigned8":"INTEGER", "unsigned16":"INTEGER", "unsigned32":"INTEGER", "unsigned64":"INTEGER",
            "signed8":"INTEGER", "signed16":"INTEGER", "signed32":"INTEGER", "signed64":"INTEGER",
            "float32":"FLOAT", "float64":"FLOAT",
            "boolean":"BOOLEAN"
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

    if options.csv:
        print("elementId,enterpriseId,name,dataType,status,description,structure,references", file=fout)

    if options.asn:
        print("SACM")
        print("DEFINITIONS IMPLICIT TAGS ::=")
        print("BEGIN")
        print("")
        print("    ContentElement ::= SEQUENCE {")
        print("        content-metaData ::= SEQUENCE {")
        print("             I DONT KNOW WHAT GOES HERE ")
        print("        },")
        print("        subjects  SEQUENCE (1..MAX) OF CHOICE {")
        print("")
        print("    SacmStatement ::= SEQUENCE {")
        print("        statementMetaData ::= SEQUENCE {")
        print("            I DONT KNOW WHAT GOES HERE ")
        print("        },")
        print("        node CHOICE {")
        print("            contentElements SEQUENCE OF (1..MAX) ContentElement")
        print("            event SEQUENCE {")
        print("                eventAttributes SEQUENCE {")
        print("                    eventName UTF8String,")
        print("                    contentElement SEQUENCE OF (1..MAX) ContentElement")
        print("                }")
        print("            }")
        print("        }")
        print("    }")

        print("    Statements ::= CHOICE {")
        for k,v in all.items():
            if v != None:
                continue
                # print("        {0}    [{1!s}] {2},".format(v.name, v.id, asn1[v.dataType] if v.dataType in asn1 else v.name), file=fout)
        print("        ...")
        print("    }")
        print("")
        

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
                if (v.dataType == "list" or v.dataType == "orderedList") and (v.tokenList != None):
                    print("<br>" + v.dataType + "(", file=fout)
                    for token in v.tokenList:
                        print(token.toString(True), file=fout)
                    print(")", file=fout)
                print("</td>", file=fout)
            elif options.csv:
                # print("elementId,enterpriseId,name,dataType,status,description,structure,references", file=fout)
                tmp = v.id + ","
                if v.enterpriseId:
                    tmp += ve.enterpriseId
                tmp += ","
                tmp += v.name + ","
                tmp += v.dataType + ","
                tmp += v.status + ","
                tmp += '"' + v.description.replace("\n", "||") + '",'
                if v.enumeration:
                    tmp += '"'
                    for ve in v.enumeration:
                        tmp += ve.name + ";"
                        if ve.tag != None:
                            tmp += ve.tag
                        tmp += ";"
                        if ve.description:
                            tmp += ve.description
                        tmp += "||"
                    tmp += '"'
                if v.tokenList != None:
                    tmp += v.dataType + "("
                    for token in v.tokenList:
                        tmp += token.toString(False)
                    tmp += ")"
                tmp += ','
                if v.references:
                    tmp += v.references
                     
                print(tmp, file=fout)
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

def CopyFile(fileName, fileOut):
    fin = open(fileName,"r");
    lines = fin.readlines()
    for line in lines:
        print(line, file=fileOut)
    fin.close()
    

def PrintError(node, text):
    if node == None:
        print("Error: {0}".format(text), file=sys.stderr)
    elif type(node) is int:
        print("Error at line {0!s}: {1}".format(node, text), file=sys.stderr)
    elif type(node) is str:
        print("Error at line {0}: {1}".format(node, text), file=sys.stderr)
    else:
        print("Error at line {0!s}: {1}".format(node.sourceline, text), file=sys.stderr)

def ASN_EmitEnumeration(v, fout):
    print("X_" + v.name + " ::= ENUMERATED {", file=fout)
    for e in v.enumeration:
        x = ""
        if e.value:
            x = "({0!s})".format(e.value)
        # print("    {0}{1},".format(e.name, x), file=fout)
    print("    ...")
    print("}")

def ASN_EmitTokenList(v, fout):
    # ordered ==> SEQUENCE
    xx = ""
    for i in v.tokenList:
        xx += i.toString(False)
    print("-- " + xx)
    seq = "CHOICE"
    for i in v.tokenList:
        if i.next and i.next != "|":
            seq = "SET"
            if v.dataType == "orderedList":
                seq = "SEQUENCE"
            break

    print("X_{0} ::= {1} {{".format(v.name, seq), file=fout)
    inChoice = False
    for i in v.tokenList:
        optional = ""
        sequence = ""
        if i.cardinality:
            if i.cardinality == "?":
                optional = "OPTIONAL"
            elif i.cardinality == "+":
                sequence = "SEQUENCE OF (1..MAX)"
            elif i.cardinality == "*":
                sequence = "SEQUENCE OF (0..MAX)"
            elif i.cardinality == ",":
                sequence = "SEQUENCE OF ({0!s}..{1!s}".format(i.minimum, self.maximum if self.maximum else "MAX")
                
        print("    {0} {3} {1} {2}{4}".format(i.element, "X_" + i.element, optional, sequence, "," if i.next else ""), file=fout)
    print("}")

if __name__ == '__main__':
    main()
