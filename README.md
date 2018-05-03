# useful-miscellaneous

A repo to store useful but miscellaneous scripts and templates etc for use with Galaxy servers.

### Echo tool and remote job running

There is a tool, a job_conf, a script for remote running of the tool and the template for the credentials to run the tool remotely.

#### simple-galaxy.py & gx-api-creds.json.template

A python script that will run a sample job on a Galaxy server that has the `echo_main_<handler-name>` tool installed on it for the various handlers. It depends on python's bioblend.
