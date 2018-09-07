---
author:
- Derek Benson
title: 'Galaxy-Dev Documentation'
---

Server Details
==============

Launch NeCTAR VM - NeCTAR Ubuntu 18.04 LTS (Bionic) amd64 through
Dashboard.

Initial Setup
=============

After deploying a new NeCTAR updates were performed and timezone set.

    for item in clean autoclean update; do apt-get $item;done
    for item in dist-upgrade autoremove; do apt-get -y $item;done

Set the timezone:

    timedatectl set-timezone "Australia/Brisbane"

Some entries were added to /etc/hosts to reduce reliance on DNS.

Planning for server and database ports as follows:

| Hostname        |        IP        |  Postgres Port  |
|:----------------|:----------------:|:---------------:|
| galaxy-dev      |  203.101.225.224 |      5960       |
| galaxy-staging  |  203.101.224.165 |      5961       |
| galaxy-prod     |  203.101.224.120 |      5962       |

Set up the firewall

    ufw allow ssh
    ufw allow from 203.101.225.224/32 to any port 5960
    ufw allow from 203.101.224.165/32 to any port 5961
    ufw allow from 203.101.224.120/32 to any port 5962
    ufw enable

Secure shared memory.

    echo =e "none\t/run/shm/\ttmpfs\tdefaults,ro\t0 0" >>/etc/fstab

Mail Setup
==========

Add packages and configure.

    apt-get install postfix mailutils libsasl2-2 ca-certificates libsasl2-modules

Add the following to /etc/postfix/main.cf

    relayhost = [smtp.gmail.com]:587
    smtp_sasl_auth_enable = yes
    smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
    smtp_sasl_security_options = noanonymous

    smtp_tls_CAfile = /etc/postfix/cacert.pem
    smtp_use_tls = yes

    inet_interfaces = loopback-only
    default_transport = smtp
    relay_transport = smtp
    inet_protocols = ipv4

Edit /etc/postfix/sasl_passwd

    [smtp.gmail.com]:587    USERNAME@gmail.com:PASSWORD

Fix permissions:

    chmod 400 /etc/postfix/sasl_passwd
    postmap /etc/postfix/sasl_passwd

Validate certificates

    cat /etc/ssl/certs/thawte_Primary_Root_CA.pem >>/etc/postfix/cacert.pem
    systemctl reload postfix

PostgreSQL Setup
================

Install postgresql.

    apt-get install postgresql postgresql-contrib postgresql-client

Set up databases

    mkdir /data && cd /data && mkdir development production staging && chown postgres:postgres *
    useradd -u 1001 -g 100 galaxy

    su - postgres -c "/usr/lib/postgresql/10/bin/initdb -D /data/production"
    su - postgres -c '/usr/lib/postgresql/10/bin/pg_ctl -D /data/production -o "-p 5962" \
    -l /var/log/postgresql/production.log start'
    su - postgres -c '/usr/lib/postgresql/10/bin/psql -p 5962 -c "CREATE ROLE galaxy LOGIN CREATEDB"'
    su - galaxy -c '/usr/lib/postgresql/10/bin/createdb -p 5962 galaxy'
    su - postgres -c "/usr/lib/postgresql/10/bin/psql -p 5962 -c \"CREATE ROLE galaxyftp LOGIN PASSWORD\
     '******'\""

    su - postgres -c "/usr/lib/postgresql/10/bin/initdb -D /data/staging"
    su - postgres -c '/usr/lib/postgresql/10/bin/pg_ctl -D /data/staging -o "-p 5961" \
    -l /var/log/postgresql/staging.log start'
    su - postgres -c '/usr/lib/postgresql/10/bin/psql -p 5961 -c "CREATE ROLE galaxy LOGIN CREATEDB"'
    su - galaxy -c '/usr/lib/postgresql/10/bin/createdb -p 5961 galaxy'
    su - postgres -c "/usr/lib/postgresql/10/bin/psql -p 5961 -c \"CREATE ROLE galaxyftp LOGIN PASSWORD \
    '******'\""

    su - postgres -c "/usr/lib/postgresql/10/bin/initdb -D /data/development"
    su - postgres -c '/usr/lib/postgresql/10/bin/pg_ctl -D /data/development -o "-p 5960" \
    -l /var/log/postgresql/development.log start'
    su - postgres -c '/usr/lib/postgresql/10/bin/psql -p 5960 -c "CREATE ROLE galaxy LOGIN CREATEDB"'
    su - galaxy -c '/usr/lib/postgresql/10/bin/createdb -p 5960 galaxy'
    su - postgres -c "/usr/lib/postgresql/10/bin/psql -p 5960 -c \"CREATE ROLE galaxyftp LOGIN PASSWORD \
    'fu5yOj2sn'\""

Enable remote access - configuration files for each database are inside
the data directory for that database e.g. /data/production

    echo "host    all             all             203.101.225.224/32      md5" >>pg_hba.conf

    # vi postgresql.conf for logging and listening on public IP address - following for production
    listen_addresses = '203.101.225.152'
    port = 5960
    log_destination = 'stderr'
    logging_collector = on
    log_directory = '/var/log/postgresql'
    log_filename = 'development.log'
    log_file_mode = 0600
    log_truncate_on_rotation = off
    log_rotation_age = 0
    log_rotation_size = 10MB

Supervisor Setup
================

Install and configure. Add username and password to main config file for
safety. Create the postgresql config file as below.

    apt-get install supervisor
    cat <<EOF>/etc/supervisor/conf.d/postgresql.conf
    [group:postgres]
    progams = prod staging dev

    [program:prod]
    command = /usr/lib/postgresql/10/bin/postgres -D /data/production -c config_file=/data/production/postgresql.conf
    process_name = prod
    autostart = true
    user = postgres
    stdout_logfile = /var/log/supervisor/postgres_prod-stdout
    stderr_logfile = /var/log/supervisor/postgres_prod-stderr
    redirect_stderr = true
    stopsignal = QUIT

    [program:staging]
    command = /usr/lib/postgresql/10/bin/postgres -D /data/staging -c config_file=/data/staging/postgresql.conf
    process_name = staging
    autostart = true
    user = postgres
    stdout_logfile = /var/log/supervisor/postgres_staging-stdout
    stderr_logfile = /var/log/supervisor/postgres_staging-stderr
    redirect_stderr = true
    stopsignal = QUIT

    [program:dev]
    command = /usr/lib/postgresql/10/bin/postgres -D /data/development -c config_file=/data/development/postgresql.conf
    process_name = dev
    autostart = true
    user = postgres
    stdout_logfile = /var/log/supervisor/postgres_dev-stdout
    stderr_logfile = /var/log/supervisor/postgres_dev-stderr
    redirect_stderr = true
    stopsignal = QUIT

    EOF

Migrating Cloudman Host Database
================================

Modify cloudman service files cm/services/apps/{galaxyreports.py
galaxy.py proftpd.py} to remove postgres as a dependency. Modify
cloudman cm/util/paths.py for new database port and make sure we return
port from psql_db_port function. Write out cloudman files.

    cd /root && mkdir CM && cd CM && tar -xzf /mnt/cm/cm.tar.gz
    # Edit files and then create tar ball and ask cloudman to store the cluster config
    cd /root/CM && tar -czf /mnt/cm/cm.tar.gz *

Modify conftemplates for proftpd.conf and reports.yml in
/opt/cloudman/config/conftemplates. Make sure to include the real
password in the ftp configuration (denoted by \*s) as cloudman will try
and generate and use a new one.

    # proftpd.conf
    $galaxy_user_name@galaxy-aust-db.genome.edu.au:$galaxy_db_port $galaxyftp_user_name ******
    # reports.yml
    postgres://galaxy:development123@galaxy-aust-db.genome.edu.au:$galaxy_db_port/galaxy

Modify galaxy.yml and galaxy.ini.backup to include the database
connection (include real password where \*s are).

    database_connection: 'postgres://galaxy:******@galaxy-aust-db.genome.edu.au:5960/galaxy'

On the database server galaxy password and galaxyftp password need to be
set.

    su - postgres -c "/usr/lib/postgresql/10/bin/psql -p 5960 -c \"ALTER ROLE galaxyftp WITH PASSWORD '******'\""
    su - postgres -c "/usr/lib/postgresql/10/bin/psql -p 5960 -c \"ALTER ROLE galaxy WITH PASSWORD '******'\""

Stop galaxy service and migrate database.

    # As the galaxy user
    mkdir /mnt/tmp/database && cd /mnt/tmp/database
    pg_dump -p 5950 galaxy >galaxy.sql
    psql -h galaxy-aust-db.genome.edu.au -p 5960 -d galaxy <galaxy.sql # and enter password for galaxy user

Check to make sure cloudman has written the tarball cm.tar.gz to cluster
bucket and reboot the server.
