#!/bin/bash
# Author:YUjichang
# Date: 2019-05-07
# Version:5.0
# description: 安装mysql

function yum_pkg() {
# 检测yum是否可用
[ $(yum repolist | awk '/repolist/{print$2}' | sed 's/,//') -eq 0 ] && echo 'your yum has problem' && exit 2

for i in $@
do
    rpm -qa | grep ${i%%.*} &>/dev/null
    [ $? -eq 0 ] || yum install -y $i &> /dev/null
    [ $? -ne 0 ] && echo 'your yum cannot install '$i && yum_right=3
done

[ $yum_right ] && exit 3
}

function create_user() {
# 创建用户
echo "start create mysql user"
useradd -s /sbin/nologin -M mysql
echo -e "create mysql user success\n"
}

function create_config() {
# 创建配置文件
cat > /etc/my.cnf << EOF
[client]
port=3306
socket=/tmp/mysql.sock

[mysqld]
server-id = 1

character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
init_connect='SET NAMES utf8mb4'

skip-external-locking
skip_name_resolve = 1

user=mysql
port=3306
basedir=$mysql_path/mysql
datadir=$mysql_path/mysql/data
tmpdir  = /tmp
socket=/tmp/mysql.sock

log_error = error.log
open-files-limit=10240
back_log=600
max_connections=2000
max_connect_errors=6000
interactive_timeout = 1800
wait_timeout = 1800

max_allowed_packet=32M
sort_buffer_size=4M
join_buffer_size=4M
thread_cache_size=300
query_cache_type=1
query_cache_size=256M
query_cache_limit=2M
query_cache_min_res_unit=16k

tmp_table_size=256M
max_heap_table_size=256M

key_buffer_size=256M
read_buffer_size=1M
read_rnd_buffer_size=16M
bulk_insert_buffer_size=64M

lower_case_table_names=1

default-time-zone='+8:00'
default-storage-engine=INNODB

innodb_buffer_pool_size=2G
innodb_log_buffer_size=32M
innodb_log_file_size=128M
innodb_flush_method=O_DIRECT

long_query_time=2
slow-query-log=on
slow-query-log-file = slow.log

expire_logs_days=7
log-bin=mysql-bin
binlog_format=ROW

[mysqldump]
quick
max_allowed_packet=32M

[mysqld_safe]
#增加每个进程的可打开文件数量
open-files-limit = 28192
EOF
}

function create_profile() {
# 创建环境变量
cat >> /etc/profile.d/mysql.sh << EOF
MYSQL_BIN_HOME=$mysql_path/mysql/bin
PATH=\$PATH:\$MYSQL_BIN_HOME
export PATH MYSQL_BIN_HOME
EOF
}

function initialize_5_7() {
# 初始化mysql
cd $mysql_path/mysql
chown -R  mysql:mysql $mysql_path/mysql/

echo -e "\nstart initialize mysql database"
bin/mysqld --initialize-insecure --user=mysql --datadir=$mysql_path/mysql/data --basedir=$mysql_path/mysql
chown -R mysql $mysql_path/mysql/data

cp support-files/mysql.server /etc/init.d/mysqld
chmod +x /etc/init.d/mysqld

create_config
create_profile

echo "start mysql database"
systemctl enable mysqld
systemctl start mysqld
}

function install_binary_5_7() {
# 二进制安装
yum_pkg bison libaio
create_user

echo "start unzip mysql binary package"
tar zxf $1 -C $mysql_path
mysql_prefix=${1%.*.*}
ln -s $mysql_path/$mysql_prefix $mysql_path/mysql
mkdir -p $mysql_path/mysql/{data,tmp}
echo

initialize_5_7
}

function ahout_help() {
# 运行说明
echo "Usage: $0 mysql file [mysql path]" && exit 1
}

# 判断是否提供mysql文件
if [ $# -lt 1 ];then
    ahout_help
fi

if [ $# -lt 2 ];then
    # 输入安装目录，默认/usr/local/mysql
    mysql_path=/usr/local
else
    mysql_path=$2
fi

install_binary_5_7 $1 && echo "install mysql success." || echo "install mysql failed."
