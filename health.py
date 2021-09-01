#!/usr/bin/env python3
import os
import sys
import xml.etree.ElementTree as ET
from packaging import version
import zipfile,fnmatch,glob
import subprocess
from optparse import (OptionParser,BadOptionError,AmbiguousOptionError)
import logging
import pathlib

#Import plugin_checker, and attempt submodule update if failure to import - as it's possible the user didn't do the pre-req steps in the README

current_path = os.getcwd()
repo_path = pathlib.Path(__file__).parent

try:
    print("Updating plugin checker...")
    os.chdir(repo_path)
    out = subprocess.Popen(['git', 'submodule', 'update', '--init', '--recursive'], stdout=subprocess.PIPE)
    for stdout_line in iter(out.stdout.readline, b''):
        print(stdout_line)
    out.stdout.close()
    return_code = out.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, ['git', 'submodule', 'update', '--init', '--recursive'])
    print("Done!")
    os.chdir(current_path)
except Exception as e:
    print("Update failed:")
    print(e)
    print("Proceeding with healthcheck using existing plugin checker directory")

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))+"/plugin_checker")
    from plugin_checker import main
except Exception as e:
    print("#######Exception#######")
    print(e)
    print("#######Exception#######")
    print("Error importing plugin_checker module. Attempting automatic submodule import with 'git submodule update --init --recursive'")
    import pathlib
    current_path = os.getcwd()
    repo_path = pathlib.Path(__file__).parent
    os.chdir(repo_path)
    try:
        out = subprocess.Popen(['git', 'submodule', 'update', '--init', '--recursive'], stdout=subprocess.PIPE)
        for stdout_line in iter(out.stdout.readline, b''):
            print(stdout_line)
        out.stdout.close()
        return_code = out.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, ['git', 'submodule', 'update', '--init', '--recursive'])
        print("#######################")
        print("Submodule update completed successfully. Please re-attempt running the script, and be sure you followed all the pre-req steps in the README")
        exit(-1)
    except Exception as e2:
        print("Automatic submodule import failed. Be sure that you went through all of the pre-reqs in the README before running this script:")
        print("""# Initialize submodule(s)
git submodule update --init --recursive

# First install plugin_checker's dependencies
cd plugin_checker
pip3 install -r requirements.txt

# Now install the main healthcheck dependencies
cd ..
pip3 install -r requirements.txt""")
        print("#######Exception#######")
        print(e2)
        print("#######Exception#######")
        exit(-1)

parser = OptionParser()
parser.add_option('-d', '--directory', dest='zipdirectory', help="Path to the folder containing the support zips", metavar="/path/to/directory/with/zips")
parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Print healthcheck parsing information to stdout before printing the health check.")
parser.add_option('-p', '--pluginpanel', action="store_true", dest='pluginpanel', default=False, help="Changes the plugin analysis from a single table to its own panel.")
options, args = parser.parse_args()

print("############################ Healthchecker Logs ############################")

if options.verbose:
    logging.basicConfig(format='%(levelname)s:\t%(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.DEBUG)
    logging.debug("Debug Logging Enabled:")
    logging.debug("Options: ")
    logging.debug(options)
    logging.debug("Args: ")
    logging.debug(args)
else:
    logging.basicConfig(format='%(levelname)s:\t%(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)

# Wish list / Improvement ideas / Work in progress
# 1. Don't skip the DB information. If one Support Zip doesn't have it, maybe the other does?
#    Line #217
# 2. Scal JVM arguments for "-XX:+HeapDumpOnOutOfMemoryError" and "-XX:HeapDumpPath=" ; call it out if they're missing
#    Line #295


#Set Current direct as root
noprops=""
skipPrintprops=False

#if specified, use directory and strip trailing slash if present
if options.zipdirectory:
    rootPath = options.zipdirectory[:-1] if options.zipdirectory.endswith("/") or options.zipdirectory.endswith("\\") else options.zipdirectory
else:
    rootPath = r"."
# look for .zip files and unzip each into its own folder using name of support.zip
pattern = '*.zip'

try:
    logging.debug("Traversing specified directory ("+rootPath+") and unzipping any .zip files found")
    for root, dirs, files in os.walk(rootPath):
        for filename in fnmatch.filter(files, pattern):
            logging.debug("Zip found: "+os.path.join(root, filename))
            extn = filename.split(".")
            # Check if the filename of the zip file exists in the list of directories. 
            if (extn[0] not in dirs):
                zipfile.ZipFile(os.path.join(root, filename)).extractall(os.path.join(root, os.path.splitext(filename)[0]))
except Exception as e:
    logging.error("Issue resolving the path containing the support zips: "+rootPath)
    logging.error(e)
    print("############################ Healthchecker Logs ############################")
    parser.print_help()
    exit(-1)

#list directories into a list. Now sure I will need it may be better to just search for files
#dirlist=list((filter(lambda x: os.path.isdir(x), os.listdir('.'))))
#print(dirlist)
#print(dirlist[0])


#search for files in all support.zips
xml_list=[]
for xml in glob.iglob(rootPath+'/**/application-properties/application.xml', recursive=True):
    logging.debug("application.xml found: "+xml)
    xml_list.append(xml)


pp_list=[]
for properties in glob.iglob(rootPath+'/**/application-config/bitbucket.properties', recursive=True):
        logging.debug("bitbucket.properties found: "+properties)
        pp_list.append(properties)

if len(pp_list) == 0:
    logging.debug("There is no bitbucket.properties file(s) in Support Zip(s) \nThis may be a containerized Instance such as Docker")
    noprops="There is no bitbucket.properties file(s) in Support Zip(s) \nThis may be a containerized Instance such as Docker"
    skipPrintprops=True

try:
    mytree = ET.parse(xml_list[0])
except:
    logging.error("We couldn't find an application.xml file based on the query: "+rootPath+"/**/application-properties/application.xml")
    print("############################ Healthchecker Logs ############################")
    parser.print_help()
    exit(-1)
myroot = mytree.getroot()

#################################Display Missing Support Zips##################
#used later to compare lists (which nodes are present and which are missing)
def Diff(li1, li2): 
    return (list(set(li1) - set(li2)))


#find if clustered
cluster=myroot.find('cluster-information/clustered')
#if true then check to see how many node in cluster and compare against zips
if cluster.text == 'true':
    checknode=myroot.find('cluster-information')
    howmanynodes=[]
    for nodes in myroot.findall('cluster-information/node'):
        howmanynodes.append(nodes)
    if len(howmanynodes) == len(xml_list):
        logging.info('All Support zips are present')
    else:
        logging.info('You have: '+str(len(howmanynodes))+' Nodes in the cluster')
        logging.info('You have: '+str(len(xml_list))+' Support Zips from the cluster')
        


        #Get names of nodes from support zips present
        foundlocal=[]
		
        for xmlfiles in xml_list:
            tree2 = ET.parse(xmlfiles)
            root2 = tree2.getroot()
           # foundlocal=[]
            if cluster.text == 'true':
                #Need to use full xpaht to node
                for getnode in root2.findall('cluster-information/node'):
                    getip=getnode.find('id')
                    getadder=getnode.find('address')
                    getlocal=getnode.find('local')
                    if getlocal.text == 'true':
                        foundlocal.append(getip.text)
                        foundlocal.append(getadder.text)                
            #print("The following nodes have been found: ",foundlocal)
 
        #get missing nodes
        othernodes=[]
        for missingNode in myroot.findall('cluster-information/node'):
            nodemissingID=missingNode.find('id')
            nodemissingAdd=missingNode.find('address')
            othernodes.append(nodemissingID.text)
            othernodes.append(nodemissingAdd.text)
                #need to compare list
        logging.info("Found the following nodes :")
        for found in foundlocal:
        	logging.info(found)
        miss=Diff(othernodes,foundlocal)
        logging.info('\n')
        logging.info("The following nodes are not present: ")
        for nothing in miss:
        	logging.info(nothing)
print("\n")
print(noprops)
print("############################ Healthchecker Logs ############################")
print('\n\n\n')

# PRINT THE DISCLAIMER

print("{panel:title=(!) Important:|borderStyle=solid|borderColor=#FF0000|titleBGColor=#FF0000|titleColor=#FFFF00|bgColor=#E7F4FA}")
print("Please be aware that health checks are not completely conclusive. We provide analysis based on the logging provided and any other details offered at the start of the health check. The health checks also do not specify whether you will or will not encounter some type of issue in the future, and therefore should not be viewed as an overall pass/fail analysis of your system.")
print("{panel}\nh6.\n----")
print('h2. Health Check')
print('(/) Ok/Good')
print('(!) Warning, may need to follow up on or keep an eye out')
print("(?) Need more information")
print("(x) Needs to be addressed / Incorrect configuration")
print("h6.")
#start table for health check
print("||Configurations & Settings||Values||")

#get product and version
prod=myroot.find('product')
#prodName is an attribute of product
prodName=prod.get('name')
#the prodVer is a list
prodVer=prod.items()
#print just product name
print("|*"+prodName+"*| |")
#check version against recommend 6.10 or below
testVer=(prodVer[1][1])
if version.parse(testVer) >= version.parse("6.10.0"):
    #print version and value
    print("|*Product Version*|(/) *"+testVer+"* Version is Good|")
else:
    print("|*Product Version*|(!) *"+testVer+"* While your version is supported. \n You should think about upgrading. \n We recommend our [Long Term Support (LTS) Release|https://confluence.atlassian.com/enterprise/atlassian-enterprise-releases-948227420.html].|")



#Check if clustered and get nodes
cluster=myroot.find('cluster-information/clustered')
if cluster.text == 'true':
    nodes=myroot.findall('cluster-information/node')
    print("|*Clustered DC Instance*\n* "+str(len(nodes))+" Nodes|", end="")
    for x in nodes:
        id=x.find('id')
        ip=x.find('address')
        print("*Node:* "+id.text)
        print("*IP:* "+ip.text)
    print("|")
else:
    print("|*Standalone Server*| |")


#Get base url / should check if proxy good
baseURL=myroot.find('bitbucket-information/base-url')
print("|*Base URL*| "+baseURL.text+"|")
# try to read props to check if proxy for standalone add later

#get bb.props/ Should make a switch to turn on or off
if skipPrintprops == True:
    print("|*bitbucket.properties*|No bitbucket.properties file|")
else:
    bbprops=open(pp_list[0],'r')
    print("|*bitbucket.properties*|{code}"+bbprops.read()+"{code}|")

#OS information
osEvn=myroot.find('operating-system')
osName=osEvn.find('os-name')
osArch=osEvn.find('os-architecture')
osVer=osEvn.find('os-version')

#check props file to see how many tickets
osPross=osEvn.find('available-processors')
osMem=osEvn.find('total-physical-memory')
osSwap=osEvn.find('total-swap-space')
osUlim=osEvn.find('max-file-descriptor')
print("|*Operating System*\n* OS\n* Version\n* Processors\n* Memory\n* Swap\n* Ulimit|*Values*\n* "+osName.text+"\n* "+osVer.text+"\n* "+osPross.text+"\n* "+osMem.text+"\n* "+osSwap.text+"\n* "+osUlim.text+"|")

#System resources
print("|*System Resources*|", end='')
for fileXML in xml_list:
    mytree1 = ET.parse(fileXML)
    myroot1 = mytree1.getroot()
    sysloalave=myroot1.find('operating-system/system-load-average')
    syscpu=myroot1.find('operating-system/system-cpu-load')
    sysfreeswap=myroot1.find('operating-system/free-swap-space')
    sysfreemem=myroot1.find('operating-system/free-physical-memory')
    openfiles=myroot1.find('operating-system/open-file-descriptor')
    foundlocal=[]
    for getnode in myroot1.findall('cluster-information/node'):
        getip=getnode.find('id')
        getadder=getnode.find('address')
        getlocal=getnode.find('local')
        if getlocal.text == 'true':
            foundlocal.append(getip.text)
            foundlocal.append(getadder.text)
    print('{panel:title=',foundlocal[0],foundlocal[1],'|borderStyle=dashed|borderColor=#3cb579|titleBGColor=#3cabb5|bgColor=#ccffcc}\n* From Support Zip:',fileXML[2:],'\n* Load Average:',sysloalave.text,'\n* CPU Load:',syscpu.text,'\n* System Memory Free:',sysfreemem.text,'\n* Swap Memory Free:',sysfreeswap.text,'\n* Open Files:',openfiles.text,'{panel}')
print('|')

# Database
# note: "database-info" element structure may be different between versions. additional checks if value is "None" needed
dbInfo=myroot.find('database-information')
if dbInfo is not None:
    dbName=dbInfo.find('database-name') 
    dbVersion=dbInfo.find('version')
    dbSupportLevel=dbInfo.find('support-level')
    dbConnUrl=dbInfo.find('connection-url')
    dbDriverName=dbInfo.find('.//driver-name')
    dbDriverVersion=dbInfo.find('.//driver-version')
    dbLabels="|*Database*"
    dbValues="|*Values*"
    if dbName is not None:
        dbLabels += "\n* Name"
        dbValues += "\n* "+dbName.text
    if dbVersion is not None:
        dbLabels += "\n* Version"
        dbValues += "\n* "+dbVersion.text
    if dbSupportLevel is not None:
        dbLabels += "\n* Support Level" 
        dbValues += "\n* "+dbSupportLevel.text
    if dbConnUrl is not None:
        dbLabels += "\n* Connection URL"
        dbValues += "\n* "+dbConnUrl.text
    if dbDriverName is not None:
        dbLabels += "\n* Driver Name"
        dbValues += "\n* "+dbDriverName.text
    if dbDriverVersion is not None:
        dbLabels += "\n* Driver Version"
        dbValues += "\n* "+dbDriverVersion.text
    print(dbLabels + dbValues + "|")

#GIT
git=myroot.find('git/version')
if version.parse(git.text) >= version.parse("2.20"):
    print('|*GIT Version*|(/) Your Git version is good: *'+git.text+'*|')
elif version.parse("2.20") >= version.parse(git.text) >= version.parse("2.11"):
    print('|*GIT Version*|(!) *While you meet the minimum requirements:* ',git.text,'\n* We recommend an upgrade to a later version 2.20+\n'+git.text+'\nPlease see our [Supported Platforms|https://confluence.atlassian.com/bitbucketserver076/supported-platforms-1026535721.html]\nAll Recommendations are based on the latest Bitbucket LTS Release.|')
else:
    print('|*GIT Version*|(x) *Unsupported Version:* ',git.text,'(x)\n* We recommend an upgrade to a later version 2.20+\nPlease see our [Supported Platforms|https://confluence.atlassian.com/bitbucketserver076/supported-platforms-1026535721.html]\nAll Recommendations are based on the latest Bitbucket LTS Release.|')

#SCM cache settings
scmhttp=myroot.find('scm-cache/http-enabled')
if scmhttp.text == 'true':
    print('|*HTTP cache*|(/) SCM cache for HTTP is *Enabled*|')
else:
    print('|*HTTP cache*|(!) SCM cache for HTTP is *Disabled*\n*Recommendation:* If possible, we recommend enabling SCM for better performance.\nThere are some configurations in which it should be disabled.\nFor more information please refer to:\n[Scaling Bitbucket for CI performance|https://confluence.atlassian.com/bitbucketserver/scaling-bitbucket-server-for-continuous-integration-performance-776640088.html]')

scmssh=myroot.find('scm-cache/ssh-enabled')
if scmssh.text == 'true':
    print('|*SSH cache*|(/) SCM cache for SSH is *Enabled*|')
else:
    print('|*SSH cache*|(!) SCM cache for SSH is *Disabled*\n*Recommendation:* If possible we recommend enabling SCM for better performance.\nThere are some configurations in which it should be disabled.\nFor more information please refer to:\n[Scaling Bitbucket for CI performance|https://confluence.atlassian.com/bitbucketserver/scaling-bitbucket-server-for-continuous-integration-performance-776640088.html]')

#Only check ref advertisement cache if version is lower than 7.3
if version.parse(testVer) < version.parse("7.3.0"):
    scmrefs=myroot.find('scm-cache/refs-advertisement/enabled')
    if scmrefs.text == 'true':
        print('|*Ref advertisement cache*|(/) SCM cache for ref advertisement is *Enabled*|')
    else:
        print('|*Ref advertisement cache*|(!) SCM cache for *ref advertisement* is *Disabled*\n*Recommendation:* If possible we recommend enabling SCM for better performance.\nThere are some configurations in which it should be disabled.\nFor more information please refer to:\n[Scaling Bitbucket for CI performance|https://confluence.atlassian.com/bitbucketserver/scaling-bitbucket-server-for-continuous-integration-performance-776640088.html]')
        print('(!) *Please note:* Ref advertisement cache is no longer applicable to Bitbucket versions 7.4 and later.|')
else:
    print("|*Ref advertisement cache*|(/) SCM cache for ref advertisement is [no longer used|https://confluence.atlassian.com/bitbucketserver/scaling-bitbucket-server-776640073.html#ScalingBitbucketServer-Caching] in Bitbucket version "+testVer+".|")
#JAVA
jv=myroot.find('java-runtime-environment/java.runtime.version')
# Marek: Automatic assessment of Java version + printing the outcome with recommendation (where applicable)
# Possible outcomes and final message of the assessment to be printed out
bad_java_version  = "|*Java Version*|(x) Your Java version *"+jv.text+"* is not supported!\nPlease refer to [Supported Platforms|https://confluence.atlassian.com/bitbucketserver076/supported-platforms-1026535721.html#Supportedplatforms-javaJava] for more information.|"
warn_java_version = "|*Java Version*|(!) *"+jv.text+"*\nJava versions 11.0.0 - 11.0.7 are not recommended due to Java bug: [JDK-8241054|https://bugs.openjdk.java.net/browse/JDK-8241054].\nWe recommended Java version 11.0.8 (or later).|"
OK_java_version   = "|*Java Version*|(/) Your Java version *"+jv.text+"* is good.\n* *Please note:* _Bitbucket Server 8.0 will raise the minimum supported Java version to 11.0.8._|"
good_java_version = "|*Java Version*|(/) Your Java version *"+jv.text+"* is good.|"
# Assessment
if (version.parse(jv.text) <= version.parse("1.8") and jv.text.find('_')<0):
    print(bad_java_version)
else:
    if version.parse(jv.text) < version.parse("1.8.0_65"):
        print(bad_java_version)
    else:
        if version.parse(jv.text) < version.parse("1.8.0_9999"):
            print(OK_java_version)
        else:
            if version.parse(jv.text) < version.parse("11"):
                print(bad_java_version)
            else:
                if version.parse(jv.text) < version.parse("11.0.8"):
                    print(warn_java_version)
                else:
                    if version.parse(jv.text) < version.parse("12"):
                        print(good_java_version)
                    else:
                        print(bad_java_version)
#get jvm args
javaParams=myroot.find('java-runtime-environment/virtual-machine-arguments')
#list jvm args/ add newlines by replacing a space with a newline
jp=javaParams.text.replace(' ', '\n')
j1=jp.replace('|','\|')
j=j1.replace('*','\*')
print("|*JVM arguments*|",j,"|")

#Put java params in a list
jplist=j.splitlines()

# Could loop through the java param list in search for "-XX:+HeapDumpOnOutOfMemoryError" and "-XX:HeapDumpPath=" ; call it out if they're missing!

#loop through list and find heap
heap=[]
for elem in jplist:
    if "Xms" in elem or "Xmx" in elem:
        heap.append(elem)
# can add check for to see if both min and max are present
# then check if they are same and recommend its for heaps under 12gb
if len(heap) == 2:
    if heap[0][4] == heap[1][4]:
        print("|*Java HEAP*|(/) *Heap Settings*\n* ", end="")
        print(','.join(heap),"|")
    else:
        print("|*Java HEAP*|(!) *Heap Settings*: " + ','.join(heap))
        print("* We recommend setting {{-Xms}} and {{-Xmx}} to the same value.|\n", end="")
else:
    print("|*Java HEAP*|(x) *Heap Settings*\n* We recommend setting {{-Xms}} and {{-Xmx}} to the same value.\n ", end="")
    print(','.join(heap),"|")


#Heap Usage

#looping thought support zips to get heap usage
print("|*Java Resources*|", end='')
for fileXML in xml_list:
    mytree1 = ET.parse(fileXML)
    myroot1 = mytree1.getroot()
    heapPercent=myroot1.find('java-runtime-environment/percent-heap-used')
    heapUsed=myroot1.find('java-runtime-environment/heap-used')
    heapAvailable=myroot1.find('java-runtime-environment/heap-available')
    #checking if clustered and find local node name
    cluster=myroot1.find('cluster-information/clustered')
    #creaete list at this level to hold the localID for node
    foundlocal=[]
    for getnode in myroot1.findall('cluster-information/node'):
        getip=getnode.find('id')
        getadder=getnode.find('address')
        getlocal=getnode.find('local')
        if getlocal.text == 'true':
            foundlocal.append(getip.text)
            foundlocal.append(getadder.text)

    print('{panel:title=',foundlocal[0],foundlocal[1],'|borderStyle=dashed|borderColor=#3C78B5|titleBGColor=#3C78B5|bgColor=#E7F4FA}\n* From Support Zip:',fileXML[2:],'\n* Heap Percentage Used:',heapPercent.text,'\n* Heap Space Free:',heapAvailable.text,'\n* Max Heap/Size:',heapUsed.text,'{panel}')
print('|')

# Filesystem - home
print("|*Filesystem -*\n*Home directory*|", end='')
for fileXML in xml_list:
    mytree1 = ET.parse(fileXML)
    myroot1 = mytree1.getroot()
    fsHome = myroot1.find('filesystem/home')
    dirName = fsHome.find('name')
    dirPath = fsHome.find('path')
    dirType = fsHome.find('type')
    dirFreeSize = fsHome.find('free-size')
    dirTotalSize = fsHome.find('total-size')
    dirFreeSizeStr = dirFreeSize.text + ' out of ' + dirTotalSize.text
    #checking if clustered and find local node name
    cluster=myroot1.find('cluster-information/clustered')
    #creaete list at this level to hold the localID for node
    foundlocal=[]
    for getnode in myroot1.findall('cluster-information/node'):
        getip=getnode.find('id')
        getadder=getnode.find('address')
        getlocal=getnode.find('local')
        if getlocal.text == 'true':
            foundlocal.append(getip.text)
            foundlocal.append(getadder.text)

    print('{panel:title=',foundlocal[0],foundlocal[1],'|borderStyle=dashed|borderColor=#3C78B5|titleBGColor=#8587FB|bgColor=#E3E4FF}\n* Name:',
        dirName.text,'\n* Path:',dirPath.text,'\n* Type:',dirType.text,'\n* Free space:',dirFreeSizeStr,'{panel}')
print('|')

# Filesystem - shared home (only need one)
print("|*Filesystem -*\n*Shared Home directory*|", end='')
fsSharedHome = myroot.find('filesystem/shared-home')
dirName = fsSharedHome.find('name')
dirPath = fsSharedHome.find('path')
dirType = fsSharedHome.find('type')
dirFreeSize = fsSharedHome.find('free-size')
dirTotalSize = fsSharedHome.find('total-size')
dirFreeSizeStr = dirFreeSize.text + ' out of ' + dirTotalSize.text
print('{panel:title=Shared Home|borderStyle=dashed|borderColor=#3C78B5|titleBGColor=#8587FB|bgColor=#E3E4FF}\n* Name:',
    dirName.text,'\n* Path:',dirPath.text,'\n* Type:',dirType.text,'\n* Free space:',dirFreeSizeStr,'{panel}')
print('|')

# Elasticsearch
es=myroot.find('Elasticsearch')
esBaseUrl=es.find('base-url')
esConnStatus=es.find('connection-result')
print("|*Elasticsearch*\n* URL\n* Status|*Values*\n*",
    esBaseUrl.text,"\n*",esConnStatus.text,"|")


if testVer[0] == 7:

    getprojects = myroot.find('projects/count')
    if getprojects != "":
        print("|*Project Count*|*",getprojects.text,"|")

    getrepos = myroot.find('repositories/count')
    if getrepos != "":
        print("|*Repository Count*|*",getrepos.text,"|")


#Call to plugin_checker.py
#Method sig:
#   main(String pathToAppXml, Boolean jiraMarkdown, Boolean verbose, Boolean tableFormat)

if options.pluginpanel:
        print("\n")
        logging.disable()
        plugin_check_success = main(xml_list[0],True,False,False)
        logging.disable(logging.NOTSET)
else:
        print("|*User-Installed Plugins*|{panel}",end='')
        logging.disable()
        plugin_check_success = main(xml_list[0],True,False,True)
        logging.disable(logging.NOTSET)
        print("{panel}|")
