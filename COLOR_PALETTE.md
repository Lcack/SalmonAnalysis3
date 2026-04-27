# SalmonAnalysis3 颜色表

Splatoon3 打工分析工具的颜色定义文档

## CSS 变量定义

所有颜色变量定义在 `styles.css` 文件顶部的 `:root` 选择器中

```css
:root {
    --splat-yellow: #E6FF00;
    --splat-yellow-dark: #C5D900;
    --splat-purple: #8B5CF6;
    --splat-orange: #FF6B35;
    --splat-pink: #FF4785;
    --splat-cyan: #00D9FF;
    --splat-black: #1a1a1a;
    --splat-dark: #2d2d2d;
    --splat-gray: #3d3d3d;
    --splat-light: #666666;
    --splat-bg: #0f0f0f;
    --text-primary: #ffffff;
    --text-secondary: #b0b0b0;
}
```

## 颜色分类

### 🎨 主色调 (Splatoon 品牌色)

| 变量名 | 色值 | 预览 | 用途 |
|--------|------|------|------|
| `--splat-yellow` | `#E6FF00` | ![#E6FF00](https://via.placeholder.com/20/E6FF00/E6FF00.png) | 主强调色、按钮、高亮、当前场次标题 |
| `--splat-yellow-dark` | `#C5D900` | ![#C5D900](https://via.placeholder.com/20/C5D900/C5D900.png) | 悬停状态、渐变结束色 |
| `--splat-purple` | `#8B5CF6` | ![#8B5CF6](https://via.placeholder.com/20/8B5CF6/8B5CF6.png) | Boss标记、当前场次持续时间背景 |
| `--splat-orange` | `#FF6B35` | ![#FF6B35](https://via.placeholder.com/20/FF6B35/FF6B35.png) | 默认标题边框、低评分、危险提示 |
| `--splat-pink` | `#FF4785` | ![#FF4785](https://via.placeholder.com/20/FF4785/FF4785.png) | (预留，目前未使用) |
| `--splat-cyan` | `#00D9FF` | ![#00D9FF](https://via.placeholder.com/20/00D9FF/00D9FF.png) | 倒计时、未来场次标题、A级评分 |

### 🌑 暗色背景系

| 变量名 | 色值 | 预览 | 用途 |
|--------|------|------|------|
| `--splat-bg` | `#0f0f0f` | ![#0f0f0f](https://via.placeholder.com/20/0f0f0f/0f0f0f.png) | 页面主背景 |
| `--splat-black` | `#1a1a1a` | ![#1a1a1a](https://via.placeholder.com/20/1a1a1a/1a1a1a.png) | 导航栏、卡片背景 |
| `--splat-dark` | `#2d2d2d` | ![#2d2d2d](https://via.placeholder.com/20/2d2d2d/2d2d2d.png) | 输入框、表格容器、卡片叠加层 |
| `--splat-gray` | `#3d3d3d` | ![#3d3d3d](https://via.placeholder.com/20/3d3d3d/3d3d3d.png) | 边框、次要背景、分隔线 |
| `--splat-light` | `#666666` | ![#666666](https://via.placeholder.com/20/666666/666666.png) | 按钮悬停、禁用状态 |

### ✏️ 文字颜色

| 变量名 | 色值 | 预览 | 用途 |
|--------|------|------|------|
| `--text-primary` | `#ffffff` | ![#ffffff](https://via.placeholder.com/20/ffffff/ffffff.png) | 主要文字、标题、重要内容 |
| `--text-secondary` | `#b0b0b0` | ![#b0b0b0](https://via.placeholder.com/20/b0b0b0/b0b0b0.png) | 次要文字、标签、提示信息 |

## 评分等级色

武器评分等级使用的独立颜色定义

### 评分等级颜色

| 等级 | 颜色值 | 预览 |
|------|--------|------|
| X | `#fbbf24` | ![#fbbf24](https://via.placeholder.com/20/fbbf24/fbbf24.png) |
| S+ | `#4ade80` | ![#4ade80](https://via.placeholder.com/20/4ade80/4ade80.png) |
| S | `#22c55e` | ![#22c55e](https://via.placeholder.com/20/22c55e/22c55e.png) |
| A | `#00D9FF` (cyan) | ![#00D9FF](https://via.placeholder.com/20/00D9FF/00D9FF.png) |
| B | `#E6FF00` (yellow) | ![#E6FF00](https://via.placeholder.com/20/E6FF00/E6FF00.png) |
| C | `#FF6B35` (orange) | ![#FF6B35](https://via.placeholder.com/20/FF6B35/FF6B35.png) |

### 评分等级徽章背景 (半透明)

| 等级 | 背景色 | 边框色 |
|------|--------|--------|
| X | `rgba(251, 191, 36, 0.3)` → `rgba(251, 191, 36, 0.1)` | `rgba(251, 191, 36, 0.5)` |
| S+ | `rgba(74, 222, 128, 0.2)` | - |
| S | `rgba(34, 197, 94, 0.2)` | - |
| A | `rgba(0, 217, 255, 0.2)` | - |
| B | `rgba(230, 255, 0, 0.2)` | - |
| C | `rgba(255, 107, 53, 0.2)` | - |

## 特殊用途颜色

### 页面标题左边框

| 标题 | 边框颜色 | 变量 |
|------|----------|------|
| 当前场次 | 橙色 | `--splat-orange` |
| 未来场次 | 青色 | `--splat-cyan` |
| 历史记录分析 | 橙色 | `--splat-orange` |
| 活动统计 | 橙色 | `--splat-orange` |
| 武器评分 | 橙色 | `--splat-orange` |

### 时间显示颜色

| 元素 | 颜色 | 变量 |
|------|------|------|
| 开始时间 | 白色 | `#ffffff` |
| 结束时间 | 白色 | `#ffffff` |
| 倒计时 | 青色 | `--splat-cyan` |
| 未来计时 | 黄色 | `--splat-yellow` |

### 评分显示颜色

| 评级 | 颜色 | 变量 |
|------|------|------|
| 高 (≥4/5) | 绿色 | `#4ade80` |
| 中 (≥3/5) | 黄色 | `--splat-yellow` |
| 低 (<3/5) | 橙色 | `--splat-orange` |

## 使用示例

### 基本使用

```css
/* 使用 CSS 变量 */
.my-element {
    color: var(--splat-yellow);
    background-color: var(--splat-dark);
    border: 2px solid var(--splat-gray);
}
```

### 渐变色

```css
/* 黄色渐变 */
.gradient-yellow {
    background: linear-gradient(135deg, var(--splat-yellow) 0%, var(--splat-yellow-dark) 100%);
}

/* 表格头部渐变 */
.table-header {
    background: linear-gradient(135deg, var(--splat-yellow) 0%, var(--splat-yellow-dark) 100%);
}
```

### 半透明背景

```css
/* 半透明叠加层 */
.overlay {
    background: linear-gradient(135deg, rgba(26, 26, 26, 0.6) 0%, rgba(45, 45, 45, 0.6) 100%);
}
```

## 修改建议

如需修改主题色，只需编辑 `styles.css` 中 `:root` 部分的变量值即可全局生效。

---
*最后更新: 2026-04-27*
