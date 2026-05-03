import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

print("读取数据中...")
df = pd.read_csv("Soil_Nutrients.csv")

print("原始数据量:", df.shape)
print("列名:", df.columns)

# =============================
# 1. 选择特征 & 目标
# =============================

target = "Yield"

numeric_features = [
    "Temperature",
    "Rainfall",
    "pH",
    "Light_Hours",
    "Light_Intensity",
    "Rh",
    "Nitrogen",
    "Phosphorus",
    "Potassium",
    "N_Ratio",
    "P_Ratio",
    "K_Ratio"
]

categorical_features = [
    "Fertility",
    "Photoperiod",
    "Category_pH",
    "Soil_Type",
    "Season"
]

features = numeric_features + categorical_features

df = df[features + [target]]

print("清洗前数据量:", df.shape)

# 删除缺失值（此时是合理的）
df = df.dropna()

print("清洗后数据量:", df.shape)

# =============================
# 2. 构建 X / y
# =============================
X = df[features]
y = df[target]

# =============================
# 3. 预处理器
# =============================
numeric_transformer = Pipeline(steps=[
    ("scaler", StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ("onehot", OneHotEncoder(handle_unknown="ignore"))
])

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features)
    ]
)

# =============================
# 4. 模型
# =============================
model = RandomForestRegressor(
    n_estimators=200,
    random_state=42,
    n_jobs=-1
)

pipeline = Pipeline(steps=[
    ("preprocessor", preprocessor),
    ("model", model)
])

# =============================
# 5. 划分数据 & 训练
# =============================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print("开始训练模型...")
pipeline.fit(X_train, y_train)

# =============================
# 6. 评估
# =============================
y_pred = pipeline.predict(X_test)

rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)

print("RMSE:", rmse)
print("R2 Score:", r2)

# =============================
# 7. 生长状态判定
# =============================
def growth_state(yield_value):
    if yield_value >= 22:
        return "生长状态：优秀"
    elif yield_value >= 18:
        return "生长状态：良好"
    else:
        return "生长状态：较差"

sample = X_test.iloc[0:1]
pred_yield = pipeline.predict(sample)[0]

print("预测产量:", pred_yield)
print(growth_state(pred_yield))