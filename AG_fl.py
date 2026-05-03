import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

print("读取数据中...")
df = pd.read_csv("Soil_Nutrients.csv")

target = "Growth_Status"

# 生长状态分类（根据产量）
def yield_to_status(y):
    if y >= 22:
        return "优秀"
    elif y >= 18:
        return "良好"
    else:
        return "较差"

df["Growth_Status"] = df["Yield"].apply(yield_to_status)

# 首先检查数据
print("\n数据信息:")
print(f"数据形状: {df.shape}")
print(f"列名: {list(df.columns)}")

# 检查 Photoperiod 列的实际内容
print("\n检查 Photoperiod 列:")
print(f"唯一值: {df['Photoperiod'].unique()}")
print(f"数据类型: {df['Photoperiod'].dtype}")
print(f"值计数:")
print(df['Photoperiod'].value_counts())

# 根据实际情况调整特征分类
# 如果 Photoperiod 是字符串，应该作为分类特征
numeric_features = [
    "Temperature", "Rainfall", "pH", "Light_Hours", "Light_Intensity",
    "Rh", "Nitrogen", "Phosphorus", "Potassium", 
    "N_Ratio", "P_Ratio", "K_Ratio"
]

# 如果 Photoperiod 是字符串，加入分类特征
categorical_features = ["Fertility", "Category_pH", "Soil_Type", "Season", "Photoperiod"]

# 选择需要的特征
selected_features = numeric_features + categorical_features + [target]
df_selected = df[selected_features].copy()

# 处理缺失值
df_selected = df_selected.dropna()

print(f"\n处理后的数据形状: {df_selected.shape}")

X = df_selected[numeric_features + categorical_features]
y = df_selected[target]

print(f"\n特征矩阵形状: {X.shape}")
print(f"目标变量分布:")
print(y.value_counts())

# 创建预处理管道
numeric_transformer = Pipeline(steps=[
    ("scaler", StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
])

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ]
)

# 创建完整管道
model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
pipeline = Pipeline(steps=[
    ("preprocessor", preprocessor),
    ("model", model)
])

# 划分训练集和测试集
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"\n训练集大小: {X_train.shape}")
print(f"测试集大小: {X_test.shape}")

# 训练模型
print("\n开始训练模型...")
pipeline.fit(X_train, y_train)

# 评估模型
y_pred = pipeline.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print(f"\n模型准确率：{accuracy:.4f}")
print("详细分类报告：")
print(classification_report(y_test, y_pred, zero_division=0))

# 保存模型
joblib.dump(pipeline, "growth_model_fixed.pkl")
print(f"\n模型已保存为: growth_model_fixed.pkl")

# 测试模型预测
print("\n测试单个样本预测...")
sample = X_test.iloc[0:1].copy()
print(f"测试样本特征:")
for col in sample.columns:
    print(f"  {col}: {sample[col].iloc[0]}")

prediction = pipeline.predict(sample)[0]
print(f"预测结果: {prediction}")
print(f"真实标签: {y_test.iloc[0]}")

if hasattr(pipeline, 'predict_proba'):
    proba = pipeline.predict_proba(sample).max()
    print(f"预测概率: {proba:.3f}")