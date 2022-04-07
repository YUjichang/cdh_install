#!/bin/bash
# Authosr:Yujichang
# date:2017-10-31
# version 1.0
# description:安装ntp服务

ntp_server=$1

function modify_conf_server() {
egrep "127.127.1.0" /etc/ntp.conf &> /dev/null
if [ $? -ne 0 ];then
    network_segment=$(echo $ntp_server | awk -F '.' '{print $1"."$2"."$3".0"}')
    sed -i.bak '21,24d' /etc/ntp.conf
    sed -i "20a server 127.127.1.0" /etc/ntp.conf
    sed -i "17a restrict $network_segment mask 255.255.255.0 nomodify notrap" /etc/ntp.conf
fi
}

function modify_conf_agent() {
egrep "$ntp_server" /etc/ntp.conf &> /dev/null
if [ $? -ne 0 ];then
    sed -i.bak '21,24d' /etc/ntp.conf
    sed -i "20a server $ntp_server" /etc/ntp.conf
fi
}

function start_service() {
systemctl status ntpd &> /dev/null
if [ $? -ne 0 ];then
    ntpdate $ntp_server &> /dev/null
    systemctl start ntpd &> /dev/null
fi
systemctl enable ntpd
}

function agent() {
yum install -y ntp &> /dev/null
modify_conf_agent
start_service
}

function server() {
yum install -y ntp &> /dev/null
modify_conf_server
start_service
}

echo $(ip addr) | grep "$ntp_server" &> /dev/null
if [ $? -eq 0 ];then
    server
else
    agent
fi
