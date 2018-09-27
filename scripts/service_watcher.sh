#!/bin/bash
# A script that checks the status of services and restarts them if they
# are unexpectedly down. If a service was stopped explicitly the watcher
# will not try to restart it. The script accepts a list of service names,
# for example: service_watcher.sh conf_snapper

TIME_FOR_LOG=`date "+%F %H:%M"`
SERVICES=$*
echo "$TIME_FOR_LOG checking status of $SERVICES"
for SERVICE in $SERVICES; do
        service $SERVICE status >> /dev/null
        RC=$?
        if [ $RC -eq 0 ]; then
                echo " - $SERVICE is alive (rc=$RC)"
        elif [ $RC -eq 3 ] || [ $RC -eq 4 ]; then
                echo " - $SERVICE was stopped by admin, not restarting (rc=$RC)"
        else
                echo " - $SERVICE is not alive, restarting (rc=$RC)"
                service $SERVICE restart
        fi
done