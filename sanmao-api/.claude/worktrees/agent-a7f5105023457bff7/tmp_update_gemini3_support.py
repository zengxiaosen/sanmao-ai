import json
import sqlite3

conn = sqlite3.connect('/opt/sanmao/sanmao-api/one-api.db')
cur = conn.cursor()

models = [
    'gemini-3-flash-preview',
    'gemini-3.1-flash-lite-preview',
    'gemini-3-pro-preview',
    'gemini-3.1-pro-preview',
    'gemini-3.1-pro-preview-customtools',
    'gemini-3-pro-image-preview',
    'gemini-3.1-flash-image-preview',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash',
    'gemini-flash-latest',
    'gemini-flash-lite-latest',
]

model_csv = ','.join(models)
cur.execute('update channels set models=? where id=4', (model_csv,))
cur.execute('delete from abilities where channel_id=4')
for model in models:
    cur.execute(
        'insert into abilities ([group], model, channel_id, enabled, priority, weight, tag) '
        "values ('default', ?, 4, 1, 0, 0, null)",
        (model,),
    )

cur.execute("select value from options where key='ModelRatio'")
ratios = json.loads(cur.fetchone()[0])
for model in [
    'gemini-3-flash-preview',
    'gemini-3.1-flash-lite-preview',
    'gemini-3-pro-preview',
    'gemini-3.1-pro-preview',
    'gemini-3.1-pro-preview-customtools',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash',
]:
    ratios.setdefault(model, 1.0)

cur.execute(
    "update options set value=? where key='ModelRatio'",
    (json.dumps(ratios, ensure_ascii=False, separators=(',', ':')),)
)
conn.commit()
print(model_csv)
print(json.dumps({model: ratios[model] for model in [
    'gemini-3-flash-preview',
    'gemini-3.1-flash-lite-preview',
    'gemini-3-pro-preview',
    'gemini-3.1-pro-preview',
    'gemini-3.1-pro-preview-customtools',
]}, ensure_ascii=False))
