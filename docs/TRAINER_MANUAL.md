# Trainer Manual

_Generated from `apps/trainer/data/manual-content.json`._

## RU

### 1. С чего начать

Тренажер нужен для одного простого цикла: выбрать кейс, посмотреть алгоритм, прокрутить его в 3D и отметить прогресс.

- Сначала выберите группу: F2L, OLL или PLL.
- Затем кликните по карточке нужного кейса в каталоге слева.
- После этого справа откроется анимация и список доступных алгоритмов для выбранного кейса.
- Если нужен свой вариант, введите формулу в поле `Enter custom algorithm...` и нажмите `Use`.

### 2. Каталог карточек

Каталог нужен для быстрого выбора кейса и управления тем, что вы сейчас учите.

- Клик по карточке открывает кейс и загружает его активный алгоритм в плеер.
- Клик по маленькой цветной точке в углу карточки меняет статус: `NEW` -> `WORK` -> `DONE`.
- Переключатель `Progress Sort` поднимает наверх кейсы, которые сейчас в работе.
- Если карточек много, сначала переключите группу, а потом уже ищите нужный кейс внутри нее.

### 3. Как управлять анимацией

3D-плеер позволяет смотреть алгоритм целиком, шагать по нему вручную и быстро перематывать нужный момент.

- `Play` запускает автопроигрывание алгоритма.
- Кнопки шагают по формуле вручную: назад к началу, шаг назад, шаг вперед.
- Кнопка скорости циклически переключает режимы `0.5`, `1`, `1.5`, `2`.
- Ползунок позволяет быстро перемотать алгоритм на любой момент.
- Если удобнее работать от формулы, кликните по нужному ходу в блоке `Active Algorithm` под плеером и переходите сразу к этому месту.

### 4. Выбор и свой алгоритм

У каждого кейса можно выбрать один из готовых алгоритмов или подставить свой собственный.

- В списке `Algorithm Selection` выберите нужный готовый вариант через radio-кнопку.
- Если стандартный вариант не нравится, введите свою формулу и нажмите `Use`.
- После применения кастомного алгоритма плеер и блок `Active Algorithm` сразу обновятся.
- Пользовательские алгоритмы можно удалять, встроенные остаются как базовые варианты.

### 5. Как вести прогресс

Статусы нужны не для красоты, а чтобы быстро отделять новые кейсы от тех, что вы уже доводите до автоматизма.

- `NEW` оставляйте для кейсов, которые еще не начали учить всерьез.
- `WORK` ставьте на то, что сейчас гоняете регулярно.
- `DONE` удобно использовать для кейсов, которые уже уверенно узнаются и исполняются.
- Менять статус можно либо в каталоге по точке на карточке, либо справа в панели деталей.

### 6. Экспорт и импорт

Если хотите перенести прогресс и свои алгоритмы в другой браузер или на другое устройство, используйте экспорт и импорт профиля.

- `Экспорт` создает код со всем вашим локальным прогрессом и выбранными алгоритмами.
- Скопируйте этот код и вставьте его через `Импорт` там, куда хотите перенести профиль.
- После импорта интерфейс сразу перестроится под новые данные.
- Это самый простой способ держать одинаковый прогресс на ноутбуке и телефоне.

### 7. Быстрые действия

Несколько клавиш помогают не тянуться каждый раз к кнопкам плеера и окна справки.

- `Space` запускает или ставит на паузу автоплей.
- `ArrowLeft` и `ArrowRight` двигают алгоритм по шагам.
- `R` возвращает анимацию в начало.
- `?` открывает справку, `Esc` закрывает справку и модальные окна.

## EN

### 1. Getting Started

The trainer is built around one simple loop: pick a case, inspect the algorithm, play it in 3D, and track your progress.

- First choose a group: F2L, OLL, or PLL.
- Then click the case card you want in the catalog on the left.
- The right side will open the animation and the list of available algorithms for that case.
- If you want your own version, type the formula into `Enter custom algorithm...` and press `Use`.

### 2. The Card Catalog

The catalog is for fast case selection and for managing what you are currently learning.

- Clicking a card opens the case and loads its active algorithm into the player.
- Clicking the small colored dot in the corner changes the status: `NEW` -> `WORK` -> `DONE`.
- `Progress Sort` pushes the cases you are actively working on to the top.
- If there are too many cards, switch the group first and then look for the case inside it.

### 3. How to Control the Animation

The 3D player lets you watch the whole algorithm, step through it manually, and jump to the exact moment you need.

- `Play` starts automatic playback.
- The transport buttons move through the formula manually: back to start, one step back, one step forward.
- The speed button cycles through `0.5`, `1`, `1.5`, and `2`.
- The slider lets you scrub to any point in the algorithm.
- If you prefer working from the formula, click the move you need in the `Active Algorithm` block below the player and jump straight there.

### 4. Picking or Typing an Algorithm

Each case can use one of the built-in algorithms or your own custom formula.

- In `Algorithm Selection`, choose the built-in option you want with the radio button.
- If you do not like the default version, type your own formula and press `Use`.
- After applying a custom algorithm, the player and the `Active Algorithm` block update immediately.
- Custom algorithms can be deleted; built-in ones remain as the base options.

### 5. Tracking Progress

Statuses are not decorative; they help you separate new cases from the ones you are actively drilling or already know.

- Use `NEW` for cases you have not really started yet.
- Use `WORK` for the cases you are currently drilling.
- Use `DONE` for cases you can already recognize and execute confidently.
- You can change the status either from the card dot in the catalog or from the detail panel on the right.

### 6. Export and Import

If you want to move your progress and custom algorithms to another browser or another device, use profile export and import.

- `Export` creates a code payload with your local progress and selected algorithms.
- Copy that code and paste it through `Import` wherever you want to restore the profile.
- After import, the interface refreshes immediately with the new data.
- This is the easiest way to keep the same progress on your laptop and phone.

### 7. Quick Actions

A few keys help you avoid reaching for the player buttons and the help window every time.

- `Space` starts or pauses autoplay.
- `ArrowLeft` and `ArrowRight` move the algorithm step by step.
- `R` returns the animation to the beginning.
- `?` opens the guide, and `Esc` closes the guide and modal windows.
