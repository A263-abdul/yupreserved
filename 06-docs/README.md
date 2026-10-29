# 06 · Docs

```
YupReserved_Project_Report.pdf   the full log + report + viva Q&A + syllabus map
                                 (same file as ~/Desktop/YupReserved Project Log/YupReserved_Project_Log.pdf)
diagrams/                        er-chen (conceptual ER), er-diagram (relational schema, from the live catalog),
                                 architecture, workflow — .dot sources, .svg and .png
report/worklog.py                one entry per working session  ← update this every session
report/viva.py                   viva questions & answers, syllabus coverage map
report/build_report.py           builds the PDF using LIVE results from the database
```

```bash
~/.yupreserved/venv/bin/python 06-docs/diagrams/build_diagrams.py
~/.yupreserved/venv/bin/python 06-docs/report/build_report.py
```
