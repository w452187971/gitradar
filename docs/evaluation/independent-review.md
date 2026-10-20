# GitRadar V4 独立审查（首次基础与种子快照）

审查者：独立代码/资料审核代理；不是人工读者或安装试用。审查日期：2026-10-20。

范围：`b70e037..5a4a5faf556d984f3d42a8a450d38c5e87517454` 的 models、github_client、observations、content、recommendations、evidence、validation；工作树 `_matchingSource` 的 exact-id 修复已观察到，并明确纳入404复现。未审查其他代理正在编写的 UI、pipeline；未修改业务或种子数据，未跑重复全套测试。报告是发现时快照，后续修复必须另行回放，不据后续改动修改首次分数。

输入快照：

- curation.json SHA256 `91e62438285b2ee315f332076ec972ab1d7e028bd76838983a9b17184e78195d`，34项目。
- seed-evidence.json SHA256 `d4861e22945697b3ec5abb001ff3230aa932da42568424bcd6d0e6159c706f51`，165条已保存官方片段。
- 核对的是保存的来源原文含义及其对应中文断言，不把hash一致或eligible=true作为语义正确证据。没有安装试用，也没有声称120样本或真实读者验收完成。

## 需要优先修正的逻辑

### P1：仓库失效与身份冲突没有贯通推荐门槛

位置：`gitradar/recommendations.py:126`、`gitradar/content.py:201`、`gitradar/observations.py:34`。

`applyObservations`把状态写在项目顶层，`_qualify`只读取不存在的`project.observation`。直接以真实LocalSend内容构造项目，在顶层分别放入`observation_status=identity_conflict`、`archived=True`、`fork=True`、`status=not_found`，四次`selectRecommendations`均为`eligible_count=1, selected_count=1`。内容门槛本身也不认识`observation_status`、archived、fork。`validation._feedErrors`虽传顶层项目，却使用同一不完整门槛，身份冲突仍漏过。必须统一真实状态契约，确认失效立即撤资格。

### P1：确认404仍沿用旧status=200

位置：`gitradar/github_client.py:307`（异常分支），`gitradar/evidence.py:49`。

复现：读取真实LocalSend bundle和curation；用`GitHubClient(transport=lambda *args: HttpResponse(404, {}, {}))`执行`readProjectEvidence`，再执行`mergeEvidence → deriveFacts → resolveContent`，时点取curation.generated_at。当前exact-id修复下，结果仍`eligible=True`，intro/install/repository/path四条状态均为200。三个GET错误虽然记录在errors，但没有落成引用或仓库的确认失效状态。网络超时可保留旧资料，已确认404必须撤资格；REST观测404同样仅变成通用failed，需传播可机器判断的原因。

### P1：复核按source_kind合并，会混淆独立文档；官网正文无法持续刷新

位置：`gitradar/evidence.py:13`、`gitradar/github_client.py:313`、`gitradar/evidence.py:80`。

exact-id分支解决了失败回退同ID误配，但正常新取数据的ID含内容hash，与seed短ID不同，仍按kind找最长README。KeePassXC的COPYING、Joplin的LICENSE、Krokiet子目录README也使用`source_kind=readme`，会被默认README覆盖并误判为变化。应按真实来源URL/文档身份取得对应内容，不能拿主README代替许可证或子文档。

首批`official_site`正文没有采集路径：client只取默认README、latest release、repository；`refreshPaths`只HEAD第一个入口，更新path_checked_at，不更新checked_at。官网平台/费用/前提片段即使页面一直有效，14天后也必然过期且当前刷新流程无法恢复；被usage_paths引用的ref在没有HEAD覆盖时7天即过期。不能用HEAD成功刷新正文时钟来规避，必须实际读取对应文档并核对断言。

### P1：自动环境判断仍会把其他主语的形态当本项目

位置：`gitradar/content.py:282`、`:299`。

最小原文：介绍为`A password manager.`；Installation为`The companion is a desktop application.
Supports Windows.
Requires an account.
[Download](https://github.com/owner/example/releases)`，再给MIT来源及新鲜日期。实际deriveFacts得到desktop_app、Windows，resolveContent自动published且eligible=True。桌面形态属于companion，不能因此给本项目普通用户GUI资格。用途锚定并未覆盖环境、前提与入口的主语；示例/代码段也不能直接成为产品声明。应将这例转回归，不用它代替未见项目盲评。

### P1：GraphQL部分字段失败把unknown降为false

位置：`gitradar/github_client.py:262`、`:291`。

节点保留合法id/name/createdAt/stargazerCount，令isArchived=null，errors.path=['r0','isArchived']。parseBatch仍返回status=success、archived=False。isFork同理。Star读取成功可以单独记录，但不能伪称仓库状态已确认；至少对影响资格的状态保留unknown/旧状态并阻止不实资格继承。

### P2：官方中文优先没有实现路径

位置：`gitradar/content.py:21`、`:88`、`:282`、`:299`。

同样合法的introduction中，`这是一个记录和整理笔记的应用。`得到purpose=None；`A note-taking application.`得到“记录和整理笔记”。当前六种用途模板均英文，平台/前提也依赖Supports/Requires英文语句；客户端不发现中文README。已有中文编辑可以覆盖，但那不等于自动优先读取官方中文。该缺口直接影响中文新项目的自动达标率，需要在全分母中计unknown，不能将中文样本剔除。

### 当前未发现需要独立阻断的额外预算/历史错误

已读预算预检、真实请求计数、重试计数、GraphQL未知成本停止、认证与身份绑定的304缓存、按UTC日期写历史及history_key保留路径。上述核心保护有明确实现；本次没有重跑全套测试，不能据此承诺全部边界无误。GraphQL成本是请求后实测，软预算允许当次越界后停止，发布校验会阻止超过600点的产物；不要宣传严格请求前点数上界。历史失败保留旧值并清增量，不等于状态已正确到达推荐层。

## 首批逐项语义核对

下表每行分别核对一个明确用途断言、平台清单、官方起始入口。用途列只评价列出的断言，不把整张卡所有细枝末节都算已审。来源ID指`data/seed-evidence.json.projects[仓库].refs`中的id，那里保存对应官方URL、片段、行号与hash。平台“未声明”不计入准确率；对待补项目仍保留分母，不能因为不合格而删掉。

路径“通过”仅说明保存资料支持该官方起始页面，**不证明该页面每个二进制资产、全部架构或安装结果已验证**。GitHub页面的“Assets Loading/error”不能充当资产级证明。

| # | 项目 | 审查用途断言 | 用途 | 平台 | 入口 | 原文定位 |
|---|---|---|---|---|---|---|
| 1 | `localsend/localsend` | 局域网传文件/文件夹/文字 | 通过 | 通过 | 通过 | install最低系统表；path拖放文件夹；intro局域网 |
| 2 | `syncthing/syncthing` | 两台以上电脑同步文件 | 通过 | 通过 | 通过 | intro Goals；requirements_1/2设备ID与GUI |
| 3 | `keepassxreboot/keepassxc` | 离线加密数据库管理账号等 | 通过 | 通过 | 通过 | intro/install Core Features；requirements_1下载 |
| 4 | `laurent22/joplin` | Markdown笔记本/待办/检索 | 通过 | 通过 | 通过 | intro；requirements_1五平台安装 |
| 5 | `obsproject/obs-studio` | 视频捕获、合成、录制、推流 | 通过 | 通过 | 通过 | intro；path三平台及系统要求 |
| 6 | `ShareX/ShareX` | 截图、标注、视频/GIF录屏 | 通过 | 通过 | 通过 | intro；install官方Downloads |
| 7 | `flameshot-org/flameshot` | 截屏并在应用内编辑 | 通过 | 通过 | 通过 | intro Features/Windows；path官方Releases |
| 8 | `Flow-Launcher/Flow.Launcher` | 搜索文件和应用并启动 | 通过 | 通过 | 通过 | intro；install Windows10+与索引 |
| 9 | `microsoft/PowerToys` | Windows日常工具集 | 通过 | 通过 | 通过 | intro Utilities；requirements_1 |
| 10 | `Stirling-Tools/Stirling-PDF` | 编辑、签署、遮盖、转换PDF | 通过 | 未声明 | 通过 | intro Key Capabilities；install Homepage |
| 11 | `marktext/marktext` | 实时Markdown编辑并导出HTML/PDF | 通过 | 通过 | 通过 | intro Features；install官方下载表 |
| 12 | `Zettlr/Zettlr` | 桌面组织和编写文稿 | 通过 | 通过 | 通过 | intro Features；install；path下载表 |
| 13 | `logseq/logseq` | 结构化笔记、任务与PDF批注 | 通过 | 未声明 | 证据不足 | intro Why Logseq；install仅截断HTML链接 |
| 14 | `giuspen/cherrytree` | 树状富文本笔记/图片表格附件 | 通过 | 通过 | 通过 | intro Features；requirements_2 Windows/Linux包 |
| 15 | `pbek/QOwnNotes` | Markdown文件笔记和待办 | 通过 | 通过 | 通过 | intro；install官方安装索引；path侧栏各平台安装 |
| 16 | `qbittorrent/qBittorrent` | BitTorrent下载和做种 | 通过 | 未声明 | 证据不足 | intro；官方主页仅有根URL，无已保存download页 |
| 17 | `FreeTubeApp/FreeTube` | YouTube桌面播放且订阅信息本地保存 | 证据不足 | 通过 | 通过 | intro支持播放但未保存本地订阅原句；install三平台 |
| 18 | `jellyfin/jellyfin` | 自建媒体服务器供终端播放 | 通过 | 通过 | 通过 | intro；requirements_1官方平台安装列表 |
| 19 | `HandBrake/HandBrake` | 已有视频转MP4/MKV/WebM | 通过 | 通过 | 通过 | intro；requirements_1与path桌面包 |
| 20 | `paulpacifico/shutter-encoder` | GUI批量视频/音频/图片转码 | 通过 | 通过 | 通过 | intro Features；install Prebuilt Binaries |
| 21 | `audacity/audacity` | 多轨音频编辑和录制 | 通过 | 通过 | 通过 | intro/install；requirements_1桌面下载 |
| 22 | `KDE/kdenlive` | 视频剪辑、家庭及复杂项目 | 通过 | 通过 | 通过 | intro；requirements_1官方下载条件 |
| 23 | `lively-community/lively` | 视频/网页动态壁纸与全屏暂停 | 通过 | 通过 | 通过 | intro Types/Performance；install安装器 |
| 24 | `files-community/Files` | Windows图形文件管理/标签/多任务 | 通过 | 通过 | 通过 | intro；install classic installer链接 |
| 25 | `WinMerge/winmerge` | 可视化文件/文件夹比较合并 | 通过 | 通过 | 通过 | intro；requirements_1/2 |
| 26 | `sindresorhus/Gifski` | 视频转GIF并调尺寸/帧率/质量 | 通过 | 通过 | 通过 | intro；install macOS26；path Get |
| 27 | `arsenetar/dupeguru` | GUI查找重复文件 | 通过 | 通过 | 通过 | intro；requirements_1官网三平台下载 |
| 28 | `qarmin/czkawka` | Krokiet GUI扫描重复及冗余文件 | 通过 | 通过 | 通过 | intro/install对照表；requirements_1 Krokiet |
| 29 | `upscayl/upscayl` | 桌面图形界面放大图片 | 通过 | 通过 | 通过 | repository用途；install三平台应用步骤 |
| 30 | `Tichau/FileConverter` | 文件右键批量转换压缩 | 通过 | 通过 | 通过 | intro；requirements_1格式表及Windows |
| 31 | `NickeManarin/ScreenToGif` | 屏幕/摄像头/画板录制与GIF/APNG等输出 | 通过 | 证据不足 | 通过 | intro；Windows仅见Store链接，未保存明确支持声明 |
| 32 | `rustdesk/rustdesk` | 远程查看控制其他电脑 | 通过 | 通过 | 通过 | intro；requirements_1支持平台和连接 |
| 33 | `cryptomator/cryptomator` | 客户端加密云盘文件 | 通过 | 通过 | 通过 | intro Introduction/repository；requirements_1 |
| 34 | `bleachbit/bleachbit` | 预览并清理文件、释放空间 | 通过 | 通过 | 通过 | intro；requirements_1 Win/Linux包 |

基础分母：34用途+31已声明平台+34入口=99项；95项获得保存原文支持（95.96%），4项证据不足，未在这99项中确认与原文直接矛盾的用途/平台/入口。证据不足为FreeTube本地订阅、ScreenToGif Windows明确支持、Logseq完整当前入口资料、qBittorrent当前download入口。后两项原本待补，保留待补是正确的；前者建议补保存原句或缩窄用途。该数值是本次固定断言的支持率，不是整卡准确率或120项目效果分数。

## 最低系统、费用、许可证与前提专项

另固定20项关键断言逐条核对，17项支持、3项与原文冲突；与上述99项不重复计断言。合并119项：112支持（94.12%）、3冲突、4证据不足。重大用途编造或明确错误第三方获取地址未在本次样本确认；许可证错标和版本渠道误导必须修正，平均分不能豁免。

| # | 断言 | 保存原文证据 | 结果 |
|---|---|---|---|
| 1 | LocalSend Win10/macOS11/Android7/iOS13 | install Compatibility逐行一致；iOS分享扩展另需14未被扩张承诺 | 支持 |
| 2 | KeePassXC Windows10/11 64位、MSVC、macOS12主下载 | requirements_1明确列出；保留旧系统备选区别 | 支持 |
| 3 | Joplin应用免费，Cloud为可选服务 | intro free及多个同步目标，Cloud链接为plans | 支持 |
| 4 | OBS Win10/11、macOS13、Ubuntu24.04 PPA | path支持声明逐项一致 | 支持 |
| 5 | OBS GPL-2.0-only | intro明确GPL v2 or any later version | **冲突：应保留or-later** |
| 6 | ShareX免费、无广告、不需账号 | intro Why ShareX三项明确声明 | 支持 |
| 7 | PowerToys Win10 2004/19041、64位、WebView2 | requirements_1 System requirements明确 | 支持 |
| 8 | Zettlr macOS12+/Windows10+且无32位 | path系统版本，install不提供32位 | 支持 |
| 9 | FreeTube选“官方正式发布版” | path列出的v0.25.3 Beta标Pre-release，install只区分official与nightly | **冲突：应写官方Beta发行版、说明非nightly** |
| 10 | HandBrake Win10+/macOS10.13+/Linux Flatpak | requirements_1与path一致 | 支持 |
| 11 | HandBrake免费且不用账号、本机运行 | path Download Safety明确 | 支持 |
| 12 | Kdenlive Win10/macOS13，daily可能损坏工程 | requirements_1对应声明 | 支持 |
| 13 | Lively GitHub安装器要求Windows10 1903 | install区分Store1809与Installer1903 | 支持 |
| 14 | Gifski当前要求macOS26 | intro/install原句，Older versions分开列出 | 支持 |
| 15 | Krokiet整应用GPL-3.0-only | license区分MIT代码与Slint GUI整应用 | 支持 |
| 16 | Upscayl需要Vulkan GPU，许多集显不工作 | install IMPORTANT原文直接支持 | 支持 |
| 17 | FileConverter转换Office文档需安装并激活Office | requirements_1格式表脚注明确 | 支持 |
| 18 | Cryptomator桌面免费，移动免费版只读且平台授权分开 | requirements_2 FAQ明确 | 支持 |
| 19 | BleachBit GPL-3.0-only | intro Licenses明确version3 or any later version | **冲突：应保留or-later** |
| 20 | BleachBit免费且不需付款/注册 | requirements_2 FAQ明确 | 支持 |

### 影响使用决策的补充缺口（不混进上述固定分数）

- **MarkText必要前提漏列**：`curation.json:840`项目中仅要求选系统/架构；其install明确macOS11与Windows10/11，path v0.22.0说明macOS builds unsigned并要求安装后处理quarantine。这是首次启动直接相关条件；应补充或限缩推荐平台，不能只称“选匹配包”。
- **FreeTube用途缺保存证据**：`curation.json:1323`的本地订阅描述没有出现在intro/install/repository/path四条片段；可能为真实功能，但本轮证据不能证明，必须补片段或删该扩展断言。
- **许可规范化风险**：OBS（`:383`）与BleachBit（`:2795`）已证实错误，其他仅用GitHub旧SPDX`GPL-2.0/GPL-3.0/AGPL-3.0`映射为`-only`的条目不能因此视为已验证精确变体。本次未把未逐项读版权授予条款的变体计入准确率；建议对同类字段做一次定点补核。
- **证据映射并不等于整bundle有来源**：FileConverter的详细音视频/文档断言主要由requirements_1支持，但purpose绑定只有intro/repository；ScreenToGif intro明示.NET9，前提映射却没有intro，curation说运行时未直接核对；应将真正支持关键断言的ref绑定到该字段。不能仅把证据堆在同一bundle就认为失效撤资格已可靠。
- **保守待补值得保留**：Stirling open-core及多子目录授权、Logseq平台未核对、qBittorrent站点获取失败、Files安装条件未知、ScreenToGif系统条件未知，五者当前review_required不应为凑数放行。qBittorrent COPYING还明确源码GPLv2+、二进制GPLv3+；如以后开放二进制路径，须区分而不能只展示源码许可。
- **原始片段质量**：Upscayl intro大段是嵌入图片base64，QOwnNotes官网片段主要为导航，若相关断言只靠这些片段应补有效段落。当前Upscayl用途由repository与install补足，不在本次用途分母判错。

## 盲评状态与保密边界

根据协调者后续指令，本轮先冻结40项目独立盲评的方法，不先挑项目、不运行实现评分以免阻塞工程修复。方法存于`/tmp/gitradar-v4-blind-reviewer/method-v1.md`，与实现工作区隔离。设计为六场景各6项+4项范围外，中文/英文、GUI/自部署/CLI/开发库/未知、新老项目交叉分层；排除34种子及开发回归家族；原文标签先于实现输出，首次评分前只公布汇总及hash。当前**40项目输入未冻结、标签未完成、首次盲评未执行**；不得将方法文件声称为已完成40或120项。未来依据盲评改规则后，这批须转回归并补未见样本。
