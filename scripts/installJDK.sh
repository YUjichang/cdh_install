#!/bin/bash
# Author: YUjichang
# Date: 2021-01-15
# version 3.0
# description:install oracle-jdk for linux

# 判断是否提供jdk文件
if [ $# -eq 0 ];then
    echo "please give jdk file" && exit 1
fi

jdk_path=/usr/java

# 检查系统是否存在openJDK，若存在，卸载
rpm -qa | egrep java &> /dev/null
if [ $? -eq 0 ];then
    for package in $(rpm -qa | grep java);do 
		rpm -e $package --nodeps
	done
fi

file=$1

# 创建安装路径
[ -e $jdk_path ] || mkdir -p $jdk_path

# 安装jdk，支持rpm和二进制包两种安装方式，建议使用二进制包安装
function install() {
jdk_suffix=${file##*.}
if [ $jdk_suffix == "rpm" ];then
    rpm -ivh --prefix=$jdk_path $file
elif [ $jdk_suffix == "gz" ];then
    tar zxf $file -C $jdk_path
else
    echo "Unable to recognize jdk file suffix" && exit 1
fi

# 获取版本号和补丁号，组成jdk父目录
jdk_version=$(echo $file | awk -F '-' '{print $2}' | awk -F 'u' '{print $1}')
jdk_patch=$(echo $file | awk -F '-' '{print $2}' | awk -F 'u' '{printf("%02d\n",$2)}')
java_home=$jdk_path/jdk1.${jdk_version}.0_${jdk_patch}

# 编写环境变量
cat >> /etc/profile.d/java.sh << EOF
JAVA_HOME=$java_home
JRE_HOME=$java_home/jre
PATH=\$PATH:\$JAVA_HOME/bin:\$JRE_HOME/bin
CLASSPATH=.:\$JAVA_HOME/lib/dt.jar:\$JAVA_HOME/lib/tools.jar:\$JRE_HOME/lib
JAVA_BIN=$java_home/bin
export PATH JAVA_HOME JRE_HOME CLASSPATH JAVA_BIN
EOF
}

install && echo "install jdk success,please run source /etc/profile later" || echo "install jdk failed"
