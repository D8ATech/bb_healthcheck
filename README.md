## This is a basic Bitbucket Health Check Script

### Prerequisites

**First you will need to install the required modules that we use to perform the healthcheck. Please run:**

```bash
# Initialize submodule(s)
git submodule update --init --recursive

# First install plugin_checker's dependencies
cd plugin_checker
pip3 install -r requirements.txt

# Now install the main healthcheck dependencies
cd ..
pip3 install -r requirements.txt
```



### How To Run

**This script is Data Center compatible**

1 - Download the support zip (or one for each node if it is Data Center) into a single target folder.

```
root$ pwd
/root/Support-Local/BBS/Test
root$ ls -l
total 2064688
-rw-r--r--@ 1 root  root  1056905701 16 Dec 18:25 Bitbucket_support_2020-12-04T15_25_42.858Z.zip
```
2 - Run the script within that folder (the one containing all the support zips). No arguments are needed.

```bash
python3 /path/to/health.py
```

3 - The script will unzip all the support zip and identify each node

```
root$ health
./Bitbucket_support_2020-12-04T15_25_42.858Z.zip
############################# Notice ############################
You have: 3  Nodes in the cluster
You have: 1  Suport Zips from cluster
Found the following nodes :
BB-Node-1
/127.0.0.1:5701


The following nodes are not present:
/127.0.0.2:5701
BB-Node-2
BB-Node-3
/127.0.0.3:5701
```

* The output of the scipt is JIRA formatted and can be copied directly into your health check ticket(text mode).

#### Additional Execution Note

If your Support Zip is already extracted, execution must be outside of the *application-properties* folder as such:

```/path/to/health.py application-properties/```

In addition the following options are also available for use:

* `-v` or `--verbose` - Enables debug/verbose output
* `-d /path/to/zip/dir` or `--directory=/path/to/zip/dir` - Specifies directory that contains the support zips to be analyzed
* `-h` or `--help` - Outputs the information you're already reading here. Look at you, smarty pants!
* `-p` or `--pluginpanel` - Outputs the plugin information in its own panel. Best for when there's lots of plugins that need attention.
