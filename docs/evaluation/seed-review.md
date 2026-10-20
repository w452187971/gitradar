# V4 首批官方资料核对

本轮核对日期：2026-10-20（具体成功请求时间见每条证据的 `checked_at`）。这是官方资料核对（`source_review`），不是实际安装、实际试用、真实读者理解测试或安全审计。

## 结果与边界

- 34 个项目保留具体中文用途、适用人群、场景、获取路径和逐项断言引用；按本轮内容模块实际解析，28 项满足推荐资料准入，6 项待复核。
- 合格项目覆盖 7 个有证据的主场景：文件转换 5、文件查找 4、文件传输 2、影音工具 5、隐私保护 3、笔记效率 6、电视桌面 3。文件传输独立归类，没有为了六类配额把 LocalSend 宣传为格式转换。
- 34 项中有 12 项已在冻结候选中；其余作为编辑种子，不能记成自动发现，也不能计入上线后 10 个自动新推荐目标。
- 使用公开 GitHub 仓库 API、官方仓库 README/许可证以及 README 或仓库主页确认的官方站点；只读取文本，没有安装或执行任何项目代码，没有使用或请求用户凭据。
- 证据文件保存 188 个有边界片段。`content_hash` 是原片段 UTF-8 文本的 SHA-256，`source_hash` 是本次读取后保存文本的 SHA-256；官方 HTML 来源先剔除脚本/样式并抽取正文文本，因此后者是规范化文本哈希，不冒充原始 HTTP 字节哈希。`start_line`、`end_line` 标记该保存文本中的范围。
- 当前仅保存官方获取说明或发布页，没有选定安装资产、核对安装包架构/签名或下载执行；`asset_verified=false`。公开 Release 存在本身未用于证明 GUI 或平台，相关事实另外引用 README 与安装文档。
- 除明确标为 `release_metadata_only` 的 Logseq 元数据请求外，仅 `entry_point_check` 非空的记录存在本轮成功入口请求；已有对应 `path` 证据含真实 `path_status=200`、`path_checked_at` 和最终跳转 URL。未成功核对的入口没有伪造成功时间。所有资料日期独立于 Star 观测，本轮没有写入或刷新 Star 历史。
- 中文受众与推荐理由属于基于官方用途的编辑判断；不会改写成官方研究结论。未明确说明费用的项目保留“未单独说明，不能承诺所有功能或服务免费”；许可证、免费声明和第三方服务费用分开。

## 影响决策的核对结果

1. **Stirling PDF 暂不推荐**：官方明确为 open-core；根 LICENSE 对 `engine/`、`frontend/editor/src/desktop/`、多个 proprietary/saas 目录规定另外许可。不能仅看 MIT 标题把整个桌面产品称为已确认开源。获取、平台、费用和许可范围仍待核。
2. **Lively 真实身份已改名**：旧 `rocksdanister/lively` 请求由 GitHub 返回当前 `lively-community/lively` 和当前 node_id。证据与编辑记录按当前 full_name 保存，另记旧别名；当前官方发布入口已独立请求。没有修改旧候选或历史键。
3. **OBS 不沿用过时最低系统**：旧官方硬件要求页仍写 macOS 11，但本轮当前下载页写 macOS 13.0+。已按当前下载路径的较新要求撰写，不合并成宽松支持。
4. **Czkawka 不混淆不同前端**：根 README 声明 GTK 版不再有新二进制，建议 Krokiet；只占一个 family，本条推荐 Krokiet。代码 MIT 与 Krokiet 完整应用 GPL-3.0-only 分开，已核对该子目录的安装与许可说明。
5. **文件转换与费用有实际限制**：File Converter 转换 Office 文档需已安装并激活 Microsoft Office；没有宣传 PDF 转 Word。Cryptomator 只选择桌面路径，明确移动免费版只读、写入授权及云盘费用分开。Joplin Cloud、RustDesk Pro 与 Upscayl Cloud 不并入本机软件承诺。
6. **仍保留不足**：Logseq 当前官网只返回网页壳，未从开发系统推断平台；qBittorrent 官方下载站请求发生 TLS 错误，未假称入口失效；Files 的最低系统与当前 classic installer 条件未补齐；ScreenToGif 的系统支持与最低 Windows 版本条件未核齐，.NET 9 运行时要求已按原 intro 补正。均等待复核，不凑推荐数量。

## 逐项目记录

| 项目 | 主场景 | 本轮资料准入 | 官方开始入口 | 限制/结论 |
| --- | --- | --- | --- | --- |
| `localsend/localsend` | 文件传输 | 合格 | [官方入口](https://github.com/localsend/localsend/releases/latest) | 官方资料核对；未试用 |
| `syncthing/syncthing` | 文件传输 | 合格 | [官方入口](https://docs.syncthing.net/intro/getting-started.html) | 官方资料核对；未试用 |
| `keepassxreboot/keepassxc` | 隐私保护 | 合格 | [官方入口](https://keepassxc.org/download/) | 官方资料核对；未试用 |
| `laurent22/joplin` | 笔记效率 | 合格 | [官方入口](https://joplinapp.org/help/install/) | 官方资料核对；未试用 |
| `obsproject/obs-studio` | 影音工具 | 合格 | [官方入口](https://obsproject.com/download) | 官方资料核对；未试用 |
| `ShareX/ShareX` | 影音工具 | 待复核 | [官方入口](https://getsharex.com/downloads) | 用途与下载事实保留；许可证出现项目源文件与根文档的版本范围差异，需先厘清整包授权。 |
| `flameshot-org/flameshot` | 笔记效率 | 合格 | [官方入口](https://github.com/flameshot-org/flameshot/releases) | 官方资料核对；未试用 |
| `Flow-Launcher/Flow.Launcher` | 文件查找 | 合格 | [官方入口](https://github.com/Flow-Launcher/Flow.Launcher/releases/latest) | 官方资料核对；未试用 |
| `microsoft/PowerToys` | 电视桌面 | 合格 | [官方入口](https://learn.microsoft.com/en-us/windows/powertoys/install) | 官方资料核对；未试用 |
| `Stirling-Tools/Stirling-PDF` | 文件转换 | 待复核 | [官方入口](https://stirling.com) | 根许可证虽有 MIT 标题，但 engine、desktop、proprietary、saas 等目录适用单独许可；本轮不进入默认开源推荐。 |
| `marktext/marktext` | 笔记效率 | 合格 | [官方入口](https://github.com/marktext/marktext/releases/latest) | 官方资料核对；未试用 |
| `Zettlr/Zettlr` | 笔记效率 | 合格 | [官方入口](https://www.zettlr.com/download) | 官方资料核对；未试用 |
| `logseq/logseq` | 笔记效率 | 待复核 | [官方入口](https://github.com/logseq/logseq/releases/tag/2.0.2) | 已补全官方发行说明证据和实际链接绑定；平台与安装前提仍待核，因此继续不进入推荐。 |
| `giuspen/cherrytree` | 笔记效率 | 合格 | [官方入口](https://www.giuspen.net/cherrytree/) | 官方资料核对；未试用 |
| `pbek/QOwnNotes` | 笔记效率 | 合格 | [官方入口](https://www.qownnotes.org/installation/) | 官方资料核对；未试用 |
| `qbittorrent/qBittorrent` | 影音工具 | 待复核 | [官方入口](https://www.qbittorrent.org) | 已删除没有保存成功页面证据的 download 深链接，仅保留原文支持的官方主页；本轮没有成功核对下载页，不推荐。 |
| `FreeTubeApp/FreeTube` | 影音工具 | 合格 | [官方入口](https://github.com/FreeTubeApp/FreeTube/releases) | 官方资料核对；未试用 |
| `jellyfin/jellyfin` | 影音工具 | 合格 | [官方入口](https://jellyfin.org/docs/general/installation/) | 官方资料核对；未试用 |
| `HandBrake/HandBrake` | 文件转换 | 合格 | [官方入口](https://handbrake.fr/downloads.php) | 官方资料核对；未试用 |
| `paulpacifico/shutter-encoder` | 文件转换 | 合格 | [官方入口](https://www.shutterencoder.com/) | 官方资料核对；未试用 |
| `audacity/audacity` | 影音工具 | 合格 | [官方入口](https://www.audacityteam.org/download/) | 官方资料核对；未试用 |
| `KDE/kdenlive` | 影音工具 | 合格 | [官方入口](https://kdenlive.org/download/) | 官方资料核对；未试用 |
| `lively-community/lively` | 电视桌面 | 合格 | [官方入口](https://github.com/lively-community/lively/releases/latest) | 官方资料核对；未试用 |
| `files-community/Files` | 文件管理 | 待复核 | [官方入口](https://files.community/download) | 用途与 Windows 桌面形态已核对；最低系统和获取入口尚未完成复核，不进入推荐。 |
| `WinMerge/winmerge` | 文件查找 | 合格 | [官方入口](https://winmerge.org/downloads/) | 官方资料核对；未试用 |
| `sindresorhus/Gifski` | 文件转换 | 合格 | [官方入口](https://sindresorhus.com/gifski) | 官方资料核对；未试用 |
| `arsenetar/dupeguru` | 文件查找 | 合格 | [官方入口](https://dupeguru.voltaicideas.net/) | 官方资料核对；未试用 |
| `qarmin/czkawka` | 文件查找 | 合格 | [官方入口](https://github.com/qarmin/czkawka/blob/master/krokiet/README.md) | 官方资料核对；未试用 |
| `upscayl/upscayl` | 文件转换 | 合格 | [官方入口](https://github.com/upscayl/upscayl/releases/latest) | 官方资料核对；未试用 |
| `Tichau/FileConverter` | 文件转换 | 合格 | [官方入口](https://file-converter.io/) | 官方资料核对；未试用 |
| `NickeManarin/ScreenToGif` | 影音工具 | 待复核 | [官方入口](https://github.com/NickeManarin/ScreenToGif/releases/latest) | 已准确记录 .NET 9 Desktop Runtime 前提并移除证据不足的 Windows 平台字段；明确系统支持仍待补核，不推荐。 |
| `rustdesk/rustdesk` | 电视桌面 | 合格 | [官方入口](https://rustdesk.com/docs/en/client/) | 官方资料核对；未试用 |
| `cryptomator/cryptomator` | 隐私保护 | 合格 | [官方入口](https://cryptomator.org/downloads/) | 官方资料核对；未试用 |
| `bleachbit/bleachbit` | 隐私保护 | 合格 | [官方入口](https://www.bleachbit.org/download) | 官方资料核对；未试用 |

## 可重做的离线核对

使用当前 `gitradar.content` 的 `deriveFacts` 与 `resolveContent`，以 `curation.generated_at` 为时点解析全部项目；逐条重算 `SHA256(ref.text.encode("utf-8"))` 与 `content_hash` 对照，并检查引用来源、绑定哈希、官方来源、新鲜度、许可、平台与关键未知项。

修订后输出为 28 个 `published` 且 `eligibility.eligible=true`，6 个 `review_required`。这只证明当前数据满足资料门槛，不能代替独立断言审查、页面实际批次、19/20 本轮 Star 观测、真实读者任务、实际安装成功或 14 天持续发现验收。没有对增长、新近创建、实际试用或免费服务作超出证据的声明。


## 独立审查后的修订记录

修订时点：2026-10-20T15:49:39.260875+00:00。独立审查首次快照与原始分数保留在 `independent-review.md`，本报告不将数据修订后的门槛数量写成独立复评成绩。

- **三处已确认冲突**：OBS 的 `license` 更正为 `GPL-2.0-or-later`，BleachBit 更正为 `GPL-3.0-or-later`，均绑定原来已保存的项目 README 授予语句及本轮实际读取的根许可证。FreeTube 的前提改成官方 Beta 发行版（保存发布页为 v0.25.3 Beta / Pre-release），明确不同于 nightly/weekly，不再称稳定正式版。
- **MarkText 前提**：原 `install` 已明确 macOS 11+、Windows 10/11、arm64/x64；原 `path` 已明确 v0.22.0 macOS 包未签名和首次启动 quarantine 处理。已将这两条真实 ref 绑定到前提，中文说明增加这些限制，没有执行相关命令或改动系统属性。
- **FreeTube 用途不足**：删除未有保存原句支持的“订阅等使用信息本地保存”，用途缩窄到原文支持的桌面 YouTube 播放与隐私目标；没有靠降低状态掩盖原错误。
- **ScreenToGif 平台不足**：移除没有明确支持原句的 Windows 平台清单与受众限定，将 `platforms=[]`；同时准确补上原 `intro` 已明示的 `.NET 9 Desktop Runtime 或以上`，前提绑定 `intro/path`。本轮尝试读取官方 Wiki Requirements Markdown 得到 404，没有将其记录成成功来源；系统与最低版本继续明确待核。
- **Logseq 入口不足**：把已有完整 `intro` 中的官方下载链接正确绑定到入口，新增真实官方 latest-release API 读取的发行身份片段 `release_entry_review`，入口改为响应明确给出的发行说明页。此请求只证明发行元数据，不是安装资产或 HTML 页面成功检查；平台、安装前提继续未知，因此仍待复核。
- **qBittorrent 入口不足**：删除没有成功页面证据的 `/download` 深链接，改为原 `intro/repository` 明确支持的官方主页，标签明确“下载页面本轮未成功核对”；不再把未知下载页当已确认开始路径。同时按保存的 COPYING 区分源码 GPLv2+ 与二进制 GPLv3+，本条桌面发行字段采用 `GPL-3.0-or-later` 并保留 OpenSSL 例外说明。依然不推荐。
- **断言绑定**：File Converter 的具体音视频/文档转换用途加入 `requirements_1` 的输入输出表，ScreenToGif 的运行时绑定真正支持它的 `intro`；事实与编辑文件中的对应字段和 claim ref IDs 均同步。
- **许可定点复核**：新增读取了 18 个项目的官方根许可证文件，并保留标题/版本片段；另保存 4 个项目的真实 README 授予段或源文件许可头。Flameshot 明确 GPLv3+、FreeTube 明确 AGPLv3 或以后版本、WinMerge 应用源文件 SPDX 明确 GPL-2.0-or-later，已分别修正。没有把通用许可证末尾的示范程序授予条款当作项目本身的 or-later 授权。
- **额外保留的许可范围不足**：ShareX 根许可证为 GPLv3，但应用 `Program.cs` 标题为 GPLv3、授予段写 GPLv2 或后续版本。不同文件与整包的范围需要区分；当前将整包精确变体设为未知、保存真实来源并暂停推荐，不删除截图用途事实。其余仅有根许可证版本证据的条目不承诺额外后续版本权利，具体来源和范围另列。
- **编辑场景**：OBS、ShareX、FreeTube、Jellyfin、Audacity、Kdenlive 统一改为“影音工具”，避免被理解成下载器。ShareX 暂待复核后，合格配额为影音工具 5、笔记效率 6、文件转换 5、文件查找 4、隐私保护 3、电视桌面 3、文件传输 2。自动模板中的“下载媒体”契约没有修改。

### 修订后的可复核结果

原始 **165 条 ref 的整个记录逐字段保持不变**，包括原文、hash、来源 URL 和 checked_at。本轮只依据真实新请求追加 **23 条 ref**，合计 **188 条**；所有保存片段的 UTF-8 SHA-256 已逐条重算，188/188 一致。未把新日期写回旧来源。来源原文 hash 一致只证明保存文本一致，不能代替语义复评。

全部 34 项的 `purpose/audience/platforms/form/prerequisites/license/cost/usage_paths` 在 facts 与 curation 中逐项相同，claim ref IDs 相同；新增 ref 的绑定 hash 已同步。以本批 `generated_at` 运行内容门槛得到 **28 合格、6 待复核**，仍超过首批至少 20 项要求。待复核为 ShareX、Stirling PDF、Logseq、qBittorrent、Files、ScreenToGif。

这是修订与门槛回放结果；本轮没有重写首次独立审查分数，没有完成独立语义复评、真实读者测试、安装试用或上线持续性验收。
