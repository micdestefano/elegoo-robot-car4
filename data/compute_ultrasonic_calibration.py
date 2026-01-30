#  Copyright (c) Michele De Stefano 2026.

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt

sns.set()

data = pd.read_csv("ultrasonic-data.csv")

G = np.c_[np.ones(len(data)), data["sensor"].values]
GtG = G.T @ G
Gtd = G.T @ data["real"].values

m = np.linalg.solve(GtG, Gtd)

x = np.linspace(0, 100, 101)
G = np.c_[np.ones(len(x)), x]
y = G @ m

print("Regression coefficients (y = q + m * x)")
print("-------------------------------------")
print(f"[q, m] = {m}")

ax = sns.lineplot(data, x="sensor", y="real", label="data")
ax.plot(x, y, label="Regression line")
ax.set_title("Real vs sensor measurement with regression")
ax.legend(loc="best")
plt.show()
