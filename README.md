# Configuration snapper 

Configuration Snapper is a simple tool for managing configuration snapshot files. The tool is available for the Ubuntu Linux distribution, and intended for use with repositories that are based on [Btrfs](https://en.wikipedia.org/wiki/Btrfs).
Snapshots are managed with cron scheduling. Two snapshots are maintained for each repository for each point in time at which a snapshot is taken. The active link location you define in the Configuration Snapper's configuration file always points to the most recent snapshot and is the location that should be used by your application.

You can add configuration stoppers to instruct the Configuration Snapper service to stop taking snapshots.

Configuration Snapper has the following functionality:

- Manages periodic repository snapshots
- Keeps the most relevant snapshot active
- Can stop snapshot updates
- Supports 1+ repositories with 1+ snapshots definitions 
- Supports 0+ stoppers

The tool is run as a service with root privileges and is self-monitored.
 
## Supported platforms / Requirements 

Supported operating systems:
- Ubuntu 12.04
- Ubuntu 14.04

Linux kernel: **3.13** is the minimum required version. **4.4** is recommended. 

## Installation

### Change configuration and create Btrfs repositories

You can use this script to create and move your snapshots into Brtfs repositories.

Prerequisite: Make sure that your OS is updated with:
```commandline
sudo apt-get update
```

Run this command: : 
```commandline
./scripts/install_fs.sh -c scripts/btrfs.conf
```
More information can be found in [Tools section](Tools).

### Configuration file

The Configuration Snapper configuration file is in json format, and enables you to define:
- Snapshot names
- Snapshot frequency
- Links for latest snapshot
- Service stoppers

Set up the service configuration file and save it in **/etc/conf_snapper/snapper_conf.json** 
A sample service configuration file: (This file can be found in the conf folder)

```json
{
    "snapper_configuration": {
        "repositories":[
            {
                "name":"repository_example",
                "path":"/var/snapper/example",
                "snapshot_levels":[
                    {
                        "name":"LongTerm",
                        "frequency":24,
                        "unit":"hour",
                        "link":"/var/snapper/example/LongTerm"
                    },
                    {
                        "name":"MedTerm",
                        "frequency":1,
                        "unit":"hour",
                        "link":"/var/snapper/example/MedTerm"
                    },
                    {
                        "name":"ShortTerm",
                        "frequency":10,
                        "unit":"min",
                        "link":"/var/snapper/example/ShortTerm"
                    }
                ]
            },
            {
                "name":"single_snapshot_configuration",
                "path":"/var/snapper/example_single",
                "snapshot_levels":[
                    {
                        "name":"LongTerm",
                        "frequency":24,
                        "unit":"hour",
                        "link":"/var/snapper/example_single/LongTerm"
                    }
                ]
            }
        ],
        "stoppers":[
            "/var/log/conf_snapper/snapper_stopper_single_snapshot_configuration.txt",
            "/var/log/conf_snapper/snapper_stopper_repository_example.txt"
        ]
    }
}
```

### Run installation.

Run this command to install Configuration Snapper.

```commandline
 bin/conf_snapper.bin 
```

## Build

If you make changes to Configuration Snapper, run this command to rebuild it, and follow the instructions.

```commandline
export BUILD_NUMBER=1 &amp;&amp; ./build/pack.sh $BUILD_NUMBER
```


## Debug

Under /var/log/conf_snapper/:
- **snapper_status.json** - A brief service status report.
- **conf_snapper.log** - The full file log, configured by default to DEBUG. The log level can be changed in conf_snapper.py using the log_level variable.

After successful installation, snapper_status.json should look like this:

```json
{
  "status": "up", 
  "hasConfigurationError": false, 
  "configurationErrorReason": "", 
  "runtimeErrorReason": "", 
  "hasRuntimeError": false
 }
```

## Tools

### confsnapper available service commands
**restart** - restart service 
<br>**start** - start service
<br>**stop** - stop service 
<br>**status** - get current service status

### Create Btrfs repository
   
**install_fs.sh** can be used for the installation / uninstallation / monitoring of a repository

```log
Usage: install_fs.sh [-htfms] -c <configuration_file>
  -h          display this help and exit       
  -t          remove Btrfs storage and exit
        -f    force remove flag for remove option
  -c          Btrfs configuration file
  -m          Monitoring Btrfs
  -s          Stop services
```

The configuration file includes everything for Btrfs repository creation and has the following format (can be found in script folder):

```log
   # File syntax (space separated):
   #   1: Name
   #   2: virtual_storage_path_which_will_be_created_or_exist
   #   3: path_to_be_mounted
   #   4: btrfs_bs
   #   5: btrfs_count
   #   6: action for existing folder in btrfs creation: umount/backup/delete
   #
   # Total Btrfs size is calculated as btrfs_bs*btrfs_count. Minimal size for Btrfs is 250M
   
   #Example for 2 repositories
   repository_example /var/snapper/example.btrfs /var/snapper/example 5M 50 delete
   single_snapshot_configuration /var/snapper/example_single.btrfs /var/snapper/example_single 5M 50 delete
```


## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

