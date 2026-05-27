# docs/research — 研究与路线图材料

本目录存放 Perilla 技术研究、场景论证与路线图评审文档，**不替代** `docs/architecture/` 中的实现级架构说明。

## 文档索引

| 文档 | 说明 |
|------|------|
| [Perilla_平台技术架构与应用场景研究报告.docx](./Perilla_平台技术架构与应用场景研究报告.docx) | 技术架构、监管/科研场景、同类对比（主报告） |
| [ROADMAP_REVIEW_APPENDIX_ZH.md](./ROADMAP_REVIEW_APPENDIX_ZH.md) | 行业化三条能力路线图 — **评审附录** |
| [PLATFORM_PRODUCT_PRINCIPLES_ZH.md](./PLATFORM_PRODUCT_PRINCIPLES_ZH.md) | 平台产品原则（能力优先、协同、易用性、导航 IA） |
| [IMPLEMENTATION_VERIFICATION_ZH.md](./IMPLEMENTATION_VERIFICATION_ZH.md) | 本轮落地核查清单与手工验收项 |

## 生成与更新

```bash
# 重新生成主报告 Word（需 python-docx）
python3 scripts/generate_perilla_research_docx.py
```

路线图附录为 Markdown 维护；若需并入 Word，可在主报告脚本中增加章节引用或二次合并。

## 使用声明

- 研究稿仅供内部规划、立项与对外技术交流参考。
- 不构成等保、密评、政务合规或产品合规认证结论。
- 落地须结合客户环境与制度要求单独评审。
