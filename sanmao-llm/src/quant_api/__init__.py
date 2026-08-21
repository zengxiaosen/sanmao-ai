"""quant_api —— 看板后端。

这个包把 sanmao-llm 跑出来的量化结果（因子、信号、回测）通过 HTTP 接口暴露出去，
供 Angular 看板调用。数据优先从 PostgreSQL 读（run_baseline 跑完会同步进去），
读不到时回退到 report_dir 下的 parquet/json 文件。

不重算任何东西：所有计算都在 run_baseline.py 里完成，这里只做“读取 + 转 JSON”。
"""
