# Pages 发布机制只读核查

截至 **2026-10-21T02:38:52Z**，没有发现 Pages 最新成功构建落后于 main HEAD。实际配置是 **legacy 分支发布，main:/**，不是自定义 artifact 部署。它存在默认Token推送的触发风险，但本次证据不能证明已发生漏发或数据因Pages停更。

## 实际证据

经现有ignored安全helper对同一公开仓库执行4次GET，均成功，无重试、无POST、未修改设置；仅输出白名单公开字段，未输出/保存凭据。

| GET | compact结果 |
| --- | --- |
| `/repos/w452187971/gitradar/pages` | build_type=`legacy`；source=`main:/`；status=`built`；站点 `https://w452187971.github.io/gitradar/` |
| `/repos/w452187971/gitradar/pages/builds?per_page=5` | 最新记录status=`built`；commit=`34f1fa623b49a775644c6c1258b53619579d6398`；created=`2026-10-20T13:25:14Z`；updated=`2026-10-20T13:26:04Z`；此前四项亦为built |
| `/repos/w452187971/gitradar/branches/main` | HEAD=`34f1fa623b49a775644c6c1258b53619579d6398`；commit时间=`2026-10-20T13:25:12Z`；author/committer=`github-actions[bot]` |
| `/repos/w452187971/gitradar/contents/.github/workflows/update.yml?ref=main` | blob SHA=`b1000c4b3504a76c62a83c8baab4d57c21bfcf0a`；checkout未覆盖默认token；有schedule/git push；无显式Pages build请求、deploy-pages步骤或pages:write |

API构建源commit与当前main完全相同，Pages状态built，因此不能把今天main尚未变化归因为Pages落后。提交author/committer只反映Git提交身份，**不能证明pusher身份或Token类型**；此次构建由何种事件/凭据或独立手动操作触发，4GET范围内没有查明。没有读取workflow运行历史、独立deployment/environment状态或CDN文件字节；这是成功build及site状态的证据，不是逐文件上线或采集新鲜度验收。GET非事务快照；结论限此时间点，不保证未来每次自动push。

## 官方机制与风险

GitHub明确说明：使用GITHUB_TOKEN的Actions提交不会触发分支式Pages构建。当前main workflow没有显式发布补偿，因此**不能依赖其默认Token push保证下一轮Pages自动更新**；最新构建已同步并不能证明这条触发链可靠。[官方发布来源说明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site#troubleshooting-publishing-from-a-branch)

官方提供 `POST /repos/{owner}/{repo}/pages/builds`，请求默认分支最新版本构建，返回201/queued；支持具有Pages写权限的App安装Token等，并对仓库和请求者的并发构建排队。它不改变Pages配置。当前workflow未授予Pages写权限，不能把contents:write当作足够权限；文档所示权限支持是方案依据，尚未用本仓库GITHUB_TOKEN调用验证。[官方Request build API](https://docs.github.com/en/rest/pages/pages#request-a-github-pages-build)

另一条官方路径是自定义artifact部署，但需要启用相应发布来源、构建/上传artifact及pages:write、id-token:write和environment，改动大于本次风险所需，不建议为此直接迁移设置。[官方自定义部署要求](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages#deploying-github-pages-artifacts)

## 下一步最小方案（未实施）

保留legacy/main:/，在既有上线授权范围内，经工程验证后仅在正式更新链上，仅对main、非诊断、验证/提升和push成功的运行显式请求一次Pages build，使用该job最小新增pages:write权限；不引入个人PAT、不靠额外空提交、不从dev/模型诊断发布。请求前确认实际推送SHA及main HEAD，记录201/queued只能算受理，随后有限核对built状态和实际构建SHA；发生并发新提交时记录差异，不把“最新分支”误称固定构建对象。403/请求失败/构建失败应作为发布未完成报告，不能写成功或无界重试。无产物变化时仍可先比较main与最近built SHA，已经相同无需重复请求。

本轮未触发构建、未申请权限、未编辑workflow/Pages或主分支。建议下一次真实main数据变化后验证该发布闭环；当前没有需要紧急重建的HEAD落后证据。
