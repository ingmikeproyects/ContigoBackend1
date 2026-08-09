import pandas as pd
import numpy as np
import os
import glob

# Rutas
MASTER_CSV = r'D:\Tesis\Datasets\tag_final_master.csv'
STUDENTLIFE_SENSING = r'D:\Tesis\Datasets\StudentLife\dataset\sensing\phonelock'

def get_real_unlocks_stats():
    print("📊 Analizando StudentLife para extraer estadísticas de desbloqueos...")
    all_files = glob.glob(os.path.join(STUDENTLIFE_SENSING, "*.csv"))

    daily_unlocks = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            if len(df) > 0:
                df['date'] = pd.to_datetime(df['start'], unit='s').dt.date
                unlocks_per_day = df.groupby('date').size()
                daily_unlocks.extend(unlocks_per_day.values)
        except:
            continue

    if not daily_unlocks:
        return 50, 20

    return np.mean(daily_unlocks), np.std(daily_unlocks)

def inject():
    if not os.path.exists(MASTER_CSV):
        print("❌ Error: No se encuentra el dataset maestro.")
        return

    print(f"📖 Cargando dataset maestro: {MASTER_CSV}")
    df = pd.read_csv(MASTER_CSV)

    mean_unlocks, std_unlocks = get_real_unlocks_stats()

    # --- RELLENO DE HUECOS CRÍTICO PARA EVITAR NaNs EN ENTRENAMIENTO ---
    print("🩹 Rellenando huecos de datos para evitar nulos...")

    # 1. Stress Level
    def fill_stress(row):
        if pd.isna(row['stress_level']):
            if row['risk_level'] == 'NORMAL': return np.random.uniform(1, 3)
            if row['risk_level'] == 'MODERATE': return np.random.uniform(4, 6)
            return np.random.uniform(7, 10)
        return row['stress_level']
    df['stress_level'] = df.apply(fill_stress, axis=1)

    # 2. Sleep Hours
    def fill_sleep(row):
        if pd.isna(row['sleep_hours']):
            if row['risk_level'] == 'SEVERE': return np.random.uniform(4, 6)
            return np.random.uniform(7, 9)
        return row['sleep_hours']
    df['sleep_hours'] = df.apply(fill_sleep, axis=1)

    # 3. Activity Level (0 a 1)
    df['activity_level'] = df['activity_level'].fillna(np.random.uniform(0.1, 0.3))

    # 4. SpO2
    def fill_spo2(row):
        if pd.isna(row['spo2']):
            if row['risk_level'] == 'SEVERE': return round(np.random.uniform(93, 96), 1)
            return round(np.random.uniform(97, 99.8), 1)
        return row['spo2']
    df['spo2'] = df.apply(fill_spo2, axis=1)

    # 5. Screen Unlocks
    def fill_unlocks(row):
        if pd.isna(row['screen_unlocks']):
            if row['risk_level'] == 'NORMAL': return max(5, int(np.random.normal(mean_unlocks, std_unlocks)))
            if row['risk_level'] == 'MODERATE': return max(15, int(np.random.normal(mean_unlocks*2, std_unlocks)))
            return max(30, int(np.random.normal(mean_unlocks*4, std_unlocks)))
        return row['screen_unlocks']
    df['screen_unlocks'] = df.apply(fill_unlocks, axis=1)

    # 6. App Usage
    df['app_usage_minutes'] = df['app_usage_minutes'].fillna(df['screen_unlocks'] * 5)

    # 7. HRV
    df['hrv'] = df['hrv'].fillna(np.random.uniform(40, 70))

    # Guardar cambios
    df.to_csv(MASTER_CSV, index=False)
    print(f"✅ Dataset maestro COMPLETO y sin huecos guardado en {MASTER_CSV}")

if __name__ == "__main__":
    inject()
