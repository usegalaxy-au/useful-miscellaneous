# Steps to setup a Pulsar server.

## Launch machine
1. Launch a `m2.xlarge` machine for the head node in a suitable zone.
    * Make it a slurm cluster only
    * Transient storage
    * No GVL utilities
    * Use cloudman key
    * Set everything else as default.

2. Check it all out.
    * Make sure that /mnt is attached.

## Install Pulsar
1. Make dir structure for pulsar
    ```sh
    sudo mkdir /mnt/pulsar
    sudo chown -R ubuntu:ubuntu /mnt/pulsar
    mkdir /mnt/pulsar/config
    mkdir -p /mnt/pulsar/files/staging
    ```
2. Create Pulsar's virtual env and activate it
    ```sh
    cd /mnt/pulsar
    virtualenv venv
    source venv/bin/activate
    ```
3. Clone the Pulsar git repo
    ```sh
    cd /mnt/pulsar
    git clone https://github.com/galaxyproject/pulsar server
    ```
4. Install the requirements
    * First, edit the requirements.txt file in the server directory and uncomment the line about drmaa.
    * Then install them
    ```sh
    cd server
    vim requirements.txt
    #Uncomment the drmaa line
    pip install -r requirements.txt
    ```
5. Copy the config files to config dir
    * The config files we need are:
        * app.yml
        * local_env.sh
        * server.ini
        * dependency_resolvers_conf.xml
        * job_metrics_conf.xml
    * Copy the sample files for each one from the `server` directory and remove the `.sample` from the ends.
6. Edit the configs
    * app.yml - just change the following lines
    * Make a really long private token. I normally use lastpass to produce one.

    ```yaml
    staging_directory: /mnt/pulsar/files/staging

    managers:
        _default_:
            type: queued_drmaa

    private_token: <your private token here>

    persistence_directory: files/persisted_data

    tool_dependency_dir: dependencies

    dependency_resolvers_config_file: /mnt/pulsar/config/dependency_resolvers_conf.xml

    ```
    * dependency_resolvers_conf.xml

    ```xml
    <dependency_resolvers>

        <conda auto_install="True" auto_init="True"/>

        <galaxy_packages versionless="true" />

        <conda versionless="true" />

    </dependency_resolvers>
    ```
    * local_env.sh
    ```sh
    ## Place local configuration variables used by the LWR and run.sh in here. For example

    ## If using the drmaa queue manager, you will need to set the DRMAA_LIBRARY_PATH variable,
    ## you may also need to update LD_LIBRARY_PATH for underlying library as well.
    export DRMAA_LIBRARY_PATH=/usr/lib/slurm-drmaa/lib/libdrmaa.so

    ## If you wish to use a variety of Galaxy tools that depend on galaxy.eggs being defined,
    ## set GALAXY_HOME to point to a copy of Galaxy.

    ## Uncomment to verify GALAXY_HOME is set properly before starting the LWR.
    #export TEST_GALAXY_LIBS=1

    ## If using a manager that runs jobs as real users, be sure to load your Python
    ## environement in here as well.
    # . .venv/bin/activate
    ```
    * server.ini

    ```
        [server:main]
        use = egg:Paste#http
        port = 8913
        host = localhost
        ssl_pem = /etc/ssl/certs/host.pem
        [app:main]
        paste.app_factory = pulsar.web.wsgi:app_factory
        app_config=/mnt/pulsar/config/app.yml
        [uwsgi]
        master = True
        paste-logger = True
        http = localhost:8913
        processes = 1
        enable-threads = True
        [watcher:web]
        cmd = chaussette --fd $(circus.sockets.web) paste:server.ini
        use_sockets = True
        numprocesses = 1
        [socket:web]
        host = localhost
        port = 8913
        ...
    ```

    * job_metrics.xml

    ```xml
    <?xml version="1.0"?>
        <job_metrics>
            <core />
            <cpuinfo verbose="true" />
            <meminfo />
            <uname />
        </job_metrics>
    </xml>
    ```

## Secure it!
1. Install some final dependencies
    ```sh
    sudo apt-get install libffi-dev python-dev libssl-dev
    pip install pyOpenSSL
    ```
2. Make a certificate and add it to the certs folder
    ```sh
    openssl genrsa 1024 > host.key
    chmod 400 host.key
    openssl req -new -x509 -nodes -sha1 -days 365 -key host.key > host.cert
    cat host.cert host.key > host.pem
    chmod 400 host.pem
    sudo cp host.pem /etc/ssl/certs/
    ```

## Start it up for the first time

1. Start it up just so it initialises conda etc
    * **Make sure the venv is still activated!**
    ```sh
    cd /mnt/pulsar/server
    ./run.sh -c /mnt/pulsar/config -m paster --daemon
    ```

2. Look at the `/mnt/pulsar/server/paster.log` logfile to make sure it's running correctly.
    * Wait for the conda installation to finish!
    * Then shut pulsar down
    ```sh
    ./run.sh -c /mnt/pulsar/config -m paster --stop-daemon
    ```

## Install letsencrypt and get a certificate for https!

1. Give your server an entry in DNS.
    * `pulsar-xxx.genome.edu.au` for example

2. Install letsencrypt.
    ```sh
    sudo add-apt-repository ppa:certbot/certbot
    sudo apt-get update
    sudo apt-get install python-certbot-nginx
    ```

3. Change nginx defaults
    ```
    sudo vim /etc/nginx/sites-enabled/default.server
    ```
    * Add the line `server_name pulsar-xxx.genome.edu.au;` just after the listen stuff in the https `server` section.


4.  Restart nginx
    ```
    sudo systemctl restart nginx
    ```

5. Obtain a certificate!
    ```
    sudo certbot --nginx -d pulsar-xxx.genome.edu.au
    ```

6.  Restart nginx again
    ```
    sudo systemctl restart nginx
    ```

**Note: You may need to make sure that the server is accessible via the net as sometimes it doesn't get the correct security groups.**

If not, then add `cloudlaunch` and `cloudman` security groups to the server in the Nectar Dashboard.

## Add the /pulsar/ redirect to the nginx config.

1. Add a file `pulsar.locations` to /etc/nginx/sites-enabled with the following contents:
    ```
    # This file is maintained by CloudMan.
    # Changes will be overwritten!

    location /pulsar {
        rewrite ^/pulsar/(.*) /$1 break;
        proxy_pass https://127.0.0.1:8913/;
        proxy_set_header   X-Forwarded-Host $host;
        proxy_set_header   X-Forwarded-For  $proxy_add_x_forwarded_for;
    }
    ```

2. Restart nginx yet again!
    ```
    sudo systemctl restart nginx
    ```

3. Check to see if nginx restarted correctly with all the new stuff!
    ```
    sudo systemctl status nginx
    ```
## Try and connect to it

1. Modify a galaxy server's `job_conf.xml` so that it sends jobs to the new server.
    * Make sure that it starts loading the deps via conda
    * see if it transfers the files
    * monitor the pulsar log and htop etc.

With any luck, it should all be done!
