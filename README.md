# vpkgj-db

Каталог для [VPKGJ](https://github.com/Risaro/vpkgj). Приложение скачивает отсюда `index.json` и картинки из `media/`, а сами файлы берёт по ссылкам из списков.

## Как устроено

```
catalog/   games.tsv  ports.tsv  translations.tsv  homebrew.tsv  plugins.tsv
media/     TITLEID/icon.png, shot1.png, shot2.png ...
index.json собирается из catalog/ скриптом
tools/     build_index.py, add.py
```

Списки это TSV: колонки разделены табом, одна строка на одну запись. Править можно руками, прямо в вебе GitHub или через `add.py`.

## Колонки

| Файл | Колонки |
|---|---|
| ports, homebrew | `titleid name version author lang vpk data data_path mirror size sha256 requires icon shots description` |
| translations | `titleid name version author lang install url mirror size sha256 requires region game_version icon shots description` |
| plugins | `id name version author url mirror size sha256 tai_section check icon shots description` |
| games | `titleid region name pkg zrif content_id size sha256 icon shots description` |

- `version`: если меняешь версию, приложение покажет «Обновление» тем, кто ставил старую.
- `data`: zip, распаковывается в `data_path` (по умолчанию `ux0:data`). Структура внутри архива сохраняется. Если архивов несколько и им нужны разные папки, пиши через `;` и `>`: `https://...usm.zip>ux0:data;https://...extra.zip>ux0:data/extra`.
- `requires`: id плагинов из `plugins.tsv` через запятую, например `kubridge,fdfix`. Перед установкой приложение смотрит `config.txt` в `ux0:tai` и `ur0:tai`. Если плагин уже прописан, пропускает, если нет, ставит сам и просит перезагрузить консоль. Переводам с `rePatch` плагин `repatch` добавляется автоматически.
- `check` у плагинов: по какой строке в `config.txt` понять, что плагин уже стоит (например `repatch`). Можно несколько через `|`. По умолчанию имя файла из ссылки.
- `install` у переводов:
  - `repatch`: zip с папкой `rePatch/TITLEID/...` или сразу с файлами игры;
  - `repatch+plugin`: то же, плюс все `.suprx` из архивов ставятся в `tai` и прописываются под `*TITLEID`;
  - `plugin`, `data`, `vpk`: отдельный плагин, data или vpk.
- `tai_section` у плагинов: `KERNEL`, `main`, `ALL` или titleid. `.skprx` всегда идёт в `*KERNEL`.
- `size`: в байтах, нужен для проверки места и отображения.
- `sha256`: для игр проверяется после загрузки, для остального пока справочно.
- `icon`, `shots`: пути внутри `media/` или полные ссылки. Для игр из списков pkgj обложки, скриншоты и описания берутся из `covers.json`, если у записи своих нет. Скриншотов несколько через `;`. Лучше 960x544, png или jpg.
- `description`: перенос строки пишется как `\n`.

## Ссылки

- Подходит обычная ссылка Google Drive вида `drive.google.com/file/d/ID/view`. Сборщик сам превращает её в прямую. Файл должен быть открыт по ссылке.
- Ссылка `github.com/.../blob/...` превращается в raw, ссылки на Releases остаются как есть.
- Запасные ссылки на один и тот же файл: через `|`, например `https://drive...|https://github.com/.../releases/...`. Приложение пробует по очереди.
- Несколько файлов в одной записи: через `;`. Например, перевод из архива rePatch и архива с плагином.
- `mirror`: ещё одна запасная ссылка. У портов она относится к data, если data есть, иначе к vpk.

У Google Drive есть лимит скачиваний на популярные файлы, поэтому большие и популярные вещи лучше класть в GitHub Releases (до 2 ГБ на файл) или давать зеркало.

## Добавить запись

```
python3 tools/add.py ports \
  --set titleid ABCD00001 --set name "Название" --set version 1.0 --set author "Автор" --set lang ru \
  --set vpk "https://github.com/.../releases/download/v1/game.vpk" \
  --set data "https://drive.google.com/file/d/ID/view" --set data_path ux0:data/game \
  --icon ~/icon.png --shot ~/1.png --shot ~/2.png
python3 tools/build_index.py
git add -A && git commit -m "Add Название" && git push
```

`add.py` копирует картинки в `media/TITLEID/`, переводит ссылки в прямые и, если сервер отдаёт размер, сам заполняет `size`. Повторный вызов с тем же titleid обновляет запись.

`build_index.py` проверяет списки и собирает `index.json`. При ошибке пишет файл и строку и ничего не собирает. С `--check-links` ещё проверяет, что все ссылки живые. GitHub Actions на каждый пуш проверяет, что `index.json` пересобран и ссылки работают.
