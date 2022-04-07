# cdh_install

> 这是一个cdh安装部署脚本，基于ansible api进行分发部署。

> 脚本自动安装了以下服务：
 1. Mysql 5.7.32
 2. JDK1.8.181
 3. Cloudera-Manager 6.3.1
 4. cdh6.3.2 parcels

注意1：parcels包替换了CDH原来的log4j包，更新到log4j2.17.1。

注意2：parcels包集成了impala3.4，默认安装版本是3.4（可选择降级到3.2）。

注意3：parcels包Hue版本升级到4.7.1，原4.4.0版本不可用。

 
## Build Setup

```bash
# 克隆项目
git clone https://github.com/Yujichang/cdh_install.git

# 安装依赖
pip install -r requirements.txt

# 修改配置文件
vim conf/hosts
vim conf/config.yml

# 安装包较大没有上传，需要下载后放到packages目录

# 安装
python main.py --install -p "PASSWORD"
```


