# Аудит визуальных систем (травы, тропинки, вода, небо, погода)

Краткий чеклист: что подключено, что не работает, куда смотреть.

---

## ✅ Работает (подключено и обновляется)

| Система | Где | Примечание |
|--------|-----|------------|
| **Небо, день/ночь** | `SkyManager` + `sky_config.json` | `app.sky_mgr` создаётся, вызывается в update. auto_cycle=true, default_time=afternoon. |
| **Облака** | `sky_config.cloud_puff` | 3 слоя, `_build_cloud_layers()` в SkyManager. |
| **Туман** | `SkyManager._fog` | `render.setFog()` в init. |
| **Вода (цвета)** | `_enhance_water_surfaces()` | Читает `water_config.json`, красит sea/river/foam. |
| **Трава (GPU)** | `_spawn_gpu_grass()` в `_build_flora_fauna()` | Патчи травы, процедурная текстура. |
| **Деревья** | `_build_flora_fauna()` | `_collect_world_model_paths("trees", [...])`. Модели могут отсутствовать. |
| **Тропинки** | `routes.serpentine_path` в layout.json + `_build_port_town()` | Сегменты mk_plane с dirt. |
| **Двери/порталы** | `location_doors` в layout.json + `_build_location_doors()` | Двери с порталами VFX, переход между локациями. |
| **Внутренние локации** | `location_meshes` + `_build_location_meshes()` | Потоковая подгрузка мешей по зонам. |

---

## ⚠️ Возможные проблемы

### 1. WeatherManager не создан
- **Код**: `weather_mgr` нигде не присваивается в app.py.
- **Использование**: только `getattr(self, "weather_mgr", None)` для `cursed_blend`.
- **Следствие**: Rain/Storm/Snow VFX не работают. День/ночь и облака идут через SkyManager, а не через WeatherManager.
- **Фикс**: создать `self.weather_mgr = WeatherManager(self)` в app и связать с SkyManager или оставить только SkyManager (он уже управляет weather_presets).

### 2. Модели деревьев/пропов могут отсутствовать
- **Ищет**: `common_tree_1.glb`, `pine_tree_1.glb`, `bush_1.glb`, `stone_1.glb` и т.д.
- **Где**: `_collect_world_model_paths()` сканирует `assets/models/`, `assets/props/`.
- **Проверка**: есть ли в проекте `assets/models/trees/`, `assets/models/props/` с нужными файлами?

### 3. Текстуры террейна
- **Terrain**: `_build_terrain()` использует процедурные материалы (mk_mat). Отдельных текстур нет.
- **Biomes**: `world_config.biomes` задаёт grass_color, fog_color. `get_biome("plains")` используется в траве.

### 4. Вода: волны и анимация
- **Подключено**: `world.update(player_pos)` вызывает `_animate_water(now)` каждый кадр — z-осцилляция по sin.

### 5. SkyManager и data_mgr
- `SkyManager` читает `app.data_mgr.sky_config` (из `sky_config.json`).
- `DataManager` загружает `sky_config.json` в `_load_file`. Проверить путь.

---

## 🔧 Быстрые проверки

1. **День/ночь**: в меню/настройках смена `sky_mgr.set_time_preset("midnight")` / `"noon"` — меняется ли освещение?
2. **Облака**: при `default_weather: "partly_cloudy"` в sky_config — видны ли облака?
3. **Трава**: после загрузки мира — есть ли зелёные патчи в поле/у замка?
4. **Вода**: река и море окрашены? Есть ли движение/волны?
5. **Двери**: подойти к дверям замка — срабатывает ли переход в Castle Interior?
6. **Тропинки**: serpentine_path идёт от замка вниз — видна ли дорога/тропа?

---

## Рекомендуемый порядок правок

1. **Проверить наличие моделей** в `assets/models/trees/`, `assets/models/props/`. При отсутствии — добавить или подставить fallback.
2. **Подключить WeatherManager** (если нужен дождь/гроза) или убрать зависимость от `weather_mgr` в update.
3. **Проверить обновление воды** — вызывается ли в каждом кадре смещение/фаза для water surfaces.
4. **Текстуры террейна** — при желании заменить процедурный материал на текстуры (grass, dirt, stone) через layout/biomes.
5. **Порталы** — `spawn_portal_vfx` вызывается при `_build_location_doors`. Убедиться, что `assets/particles/portal_rift.ptf` существует.

---

## Файлы для правок

| Задача | Файлы |
|--------|-------|
| WeatherManager | `src/app.py` (создание), `src/world/weather_manager.py` |
| Небо/погода | `data/sky_config.json`, `src/managers/sky_manager.py` |
| Вода | `data/water_config.json`, `src/world/sharuan_world.py` (_enhance_water, _build_sea, _build_river) |
| Трава/деревья | `src/world/sharuan_world.py` (_build_flora_fauna), `data/world_config.json` (biomes) |
| Тропинки | `data/world/layout.json` (routes), `src/world/sharuan_world.py` (_build_port_town, _build_scenery) |
| Двери/порталы | `data/world/layout.json` (location_doors), `src/world/sharuan_world.py` (_build_location_doors) |
