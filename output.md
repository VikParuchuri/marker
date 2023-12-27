
## 博流板卡-云端配置流程 购买云服务器

我们可以使⽤腾讯云来进⾏代码的运⾏。点击链接,注册或者登陆腾讯云账号,进⼊购买界⾯。 我们这⾥选择⾃定义配置,按照需要时间选择计费模式。
在地域中选择欧洲和美洲-硅⾕;
![IM11.png](temp files/IM11.png)
选择1核1GB或者2核2GB的实例;
![IM12.png](temp files/IM12.png)
![IM21.png](temp files/IM21.png)
选择Ubuntu系统,并选择64位-版本20.04或者22.04的镜像;然后点击下⼀步。

## ![Im22.Png](Temp Files/Im22.Png) 配置云服务器⽹络

选择⽹络VPC,其他设置选择默认;
![IM23.png](temp files/IM23.png)
选择安全组,常⽤IP/端⼝全部勾选;
![IM27.png](temp files/IM27.png)
输⼊实例的名称,选择登录⽅式,设置密码;其他选项默认,然后点击下⼀步。
![IM28.png](temp files/IM28.png)
![IM29.png](temp files/IM29.png)
浏览所有的配置,同意协议,选择⽴即购买。
![IM33.png](temp files/IM33.png)
![IM34.png](temp files/IM34.png)
使⽤微信扫码或者银⾏卡⽀付等⽅式购买之后,可以进⼊到云服务器界⾯,点击链接,进⼊总控台。 在左边的菜单栏中选择实例,就可以看到右边刚刚创造好的实例,点击实例名称处的链接进⼊实例界⾯;
![IM35.png](temp files/IM35.png)
这⾥我们可以看到刚刚⾃定义名称建⽴好的实例,选择登录;

按照设置的登录⽅式进⾏登录;

## ![Im42.Png](Temp Files/Im42.Png) ![Im42.Png](Temp Files/Im42.Png)

进⼊终端界⾯之后,选择左上⻆的⽂件夹标志,就可以上传相应的代码了。

 

## Api配置

![IM27.png](temp files/IM27.png)
![IM28.png](temp files/IM28.png)

## 服务管理

⾸先创建服务,点击API⽹关-服务-新建。

## ![Im55.Png](Temp Files/Im55.Png)

选择基本信息配置,选择共享型

选择前端为http和https,选择⾃⼰的云服务器。访问⽅式为了⽅便测试公⽹和内⽹都勾选了。

这个所属VPC和实例的⽹络信息⼀致。

建好界⾯⻓这样。

## ![Im70.Png](Temp Files/Im70.Png) 获取服务域名

在API⽹关-服务-点击刚建好的服务后,选择基础配置后出现了以下⻚⾯

可以获得访问地址 http://service-nxyj557c-1319330417.usw.apigw.tencentcs.com:80  。

## 创建Api

在刚才的⻚⾯中,点击管理API后可以看到chatbot_api暂时还是空的。点击新建创建API。

给API命名,然后选择前端类型为HTTP&HTTPS。路径这⾥我不确定应该写什么,填写了 / 。

请求⽅法因为云端主要测试 chatapi;asrapi;ttsapi 这⼏个post,就选择了这个。其他都是默认值。然后点击下
⼀步
![IM82.png](temp files/IM82.png)
教程中可以看到通⽤API中还有公⽹URL/IP,但是可能因为配置服务的时候选择了VPC,就只有了这四个选项。
![IM83.png](temp files/IM83.png)
选择了通过后端VPC通道对接,然后选择⼀开始服务中建⽴的通道。后端路径仍然选择了 / ,但是我不是⾮常确 定。请求⽅法和前⾯部分同理选择了POST。点击下⼀步。

这⼀部分我选择都是默认值。点击完成。

## ![Im88.Png](Temp Files/Im88.Png)

提示需要发布服务API配置才能⽣效,点击发布服务。

## ![Im92.Png](Temp Files/Im92.Png) G) Rse, Apirbdeeer 调试Api

在刚刚的管理API界⾯点击新建好的 api-f267hlg4  ,选择右边界⾯的API调试。在/release旁边的"/"路径中写 上/chatapi,添加输⼊⽂本。

## ![Im93.Png](Temp Files/Im93.Png)

€ 
   - service-nxyj557¢ 
                          - chatbot 
                                   api 
                                       HE 

He 

                                                              RECS 
                                                                       RA SIE 
                                            We df 
                                                eS 
'BUZAPI 
        Bilas 
                 (FRI 
                     XI) 
                          AEWA 
                                    BRS Be 
                                            Hite 
                                                     EIT 

+m2@ 
      LEX 
             F 
                    WW 

api-f267hlg4 
              icsti 
                    VPCAAIR 
                                                                                                 Am ai 
                                                                                                           4at8 

BAMER 
          ALEC 
                     fat See 
                               APIiit 

                                                  POST 
                                                         vy _ 
                                                             http:// 
                                                                   y 
                                                                      _ service-nxyj557c-1319330417.usw.apigw.tencentcs.com 
                                                                                                                           vy 
                                                                                                                               /release 
                                                                                                                                       vy 
                                                                                                                                           /chata 
                                                                                                                                                       RK 
api-f267hlg4 
            test1 

POST / 
                                                 Params 
                                                              Body (1) 
                                                                           Headers 
                                                                                         Cookies 
                                                                                                      Auth 
                                                                                                                                       Powered by & Apifox 

none 
           form-data 
                            x-www-form-urlencoded 
                                                         (©) json 
                                                                        xml 
                                                                                   raw 
                                                                                             binary 

1 
          ¢{ 
                                                                                                                                                                                                                                     = 
2 
                     "text": 
                                            "hello! !" 
                                                                                                                                                                                                                                              cs 

3 
          } 

20 
    v 
                             1 
                                    /1R

添加openai的授权key,这⾥使⽤的是和python⽂件⾥⼀样的key(换过别的key但是效果⼀样)。输出和报错如 下:**503 Service Unavaliable**。
wc x(t © 
v 
![IM97.png](temp files/IM97.png)
前端试过https或者http,都有⼀样的报错。期间云端运⾏log没有更新,猜测可能是以上的部署有出现问题,没有
连接到⽬标的云服务器。
![IM98.png](temp files/IM98.png)