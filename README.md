# GitRadar 中文 GitHub 爆款雷达

一个可通过 GitHub Pages 免费部署的中文开源项目发现网页原型。

## 部署（GitHub 用户名：w452187971）

1. 在 GitHub 创建 **Public** 仓库，建议命名为 `gitradar`。
2. 上传本压缩包内的文件到仓库根目录（包括隐藏的 `.github` 文件夹）。
3. 打开仓库 **Settings → Pages**。
4. 在 **Build and deployment** 下选择 **Deploy from a branch**。
5. 选择 `main` 分支、`/(root)` 文件夹，点击 **Save**。
6. 等待 Pages 完成发布，访问：
   `https://w452187971.github.io/gitradar/`

## 目前版本说明

- 浏览器打开时通过 GitHub 公开 Search API 获取候选项目。
- 显示中文分类、简短规则生成的中文说明、搜索、收藏、排序。
- **不是**真正的每日 Star 飙升排行榜。首次使用没有历史增长数据；
  同一浏览器后续访问可比较与首次记录的 Star 数量。
- GitHub API 有未登录请求频率限制；请求失败时尝试显示浏览器缓存。
- GitHub Pages 是静态托管；网站不会自动在后台采集数据。
- 不需要填写邮箱、密码或个人访问令牌。
- 不保证 GitHub Pages 在所有地区均可访问。

## 下一阶段

增加 GitHub Actions 定时采集、仓库历史快照、7 天增量榜和 AI 中文摘要。
