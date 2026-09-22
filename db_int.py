import pandas as pd
import sqlite3

conn =  sqlite3.connect('BIC DB')
cursor = conn.cursor()

file = './CBS Swift Inward/BICDIR2018_V1_FULL_20231229.txt'
df = pd.read_csv(file, sep='\t', header=0)
df.to_sql('BIC', con=conn, if_exists='replace', index=False)
# conn.commit()
# df2 = pd.read_sql('SELECT * FROM BIC', con=conn)
# print(df2.head())