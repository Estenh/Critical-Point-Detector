import pandas as pd
import statistics

df = pd.read_csv('stats.csv')
print(df.tail(30))
summary = df.groupby('name').agg({'geo_time': ['mean', statistics.stdev], 'cp_time': ['mean', statistics.stdev]})
print(summary)
