# Trainer Manual

_Generated from `apps/trainer/data/manual-content.json`._

## RU

### 1. Что это за тренажер

Rubik Motion Trainer объединяет каталог кейсов, 3D-плеер алгоритмов и быстрые инструменты обучения в одном адаптивном интерфейсе.

- Desktop и mobile больше не разделены по разным интерфейсам: используется один entrypoint и один набор экранов.
- Каталог кейсов всегда остается источником выбора, а правая часть интерфейса отвечает за разбор и проигрывание алгоритма.
- Справка доступна прямо из интерфейса через кнопку Help или по горячей клавише '?'.

### 2. Адаптивный layout

Интерфейс автоматически перестраивается под ширину экрана, но режим можно зафиксировать query-параметром `?layout=`.

- Desktop: каталог и детали видны одновременно.
- Tablet: каталог и детали остаются на одном экране, но layout становится более вертикальным.
- Mobile: каталог и детали переключаются как отдельные представления; панель статуса и алгоритмов открывается через Settings.
- Для принудительной проверки интерфейса используйте `?layout=desktop`, `?layout=mobile` или оставьте `?layout=auto`.

### 3. Работа с каталогом

Каталог показывает кейсы выбранной группы и позволяет быстро менять приоритеты обучения.

- Вкладки F2L / OLL / PLL переключают активную группу без перезагрузки страницы.
- Progress Sort меняет порядок карточек так, чтобы сначала шли кейсы в работе.
- Нажатие на цветную точку карточки циклически переключает статус NEW -> IN_PROGRESS -> LEARNED.
- Нажатие на саму карточку открывает детали кейса и загружает текущий активный алгоритм в sandbox.

### 4. Управление 3D-плеером

Sandbox воспроизводит алгоритм пошагово и позволяет разбирать формулу как непрерывную timeline-анимацию.

- Кнопки ⏮, ⏪, ▶, ⏩ возвращают в начало, двигают по шагам и запускают/останавливают проигрывание.
- Скорость `x1`, `x1.5`, `x2` меняет tempo проигрывания без смены активного алгоритма.
- Timeline slider позволяет быстро перейти к произвольному моменту внутри последовательности.
- Активный шаг подсвечивается и в плеере, и в блоке Active Algorithm под видео.

### 5. Выбор и добавление алгоритмов

Для каждого кейса можно переключать предзагруженные алгоритмы и добавлять собственные варианты.

- Radio-переключатель делает выбранный алгоритм активным и сразу перезагружает timeline.
- Собственные алгоритмы вводятся в поле `Enter custom algorithm...` и применяются кнопкой Use.
- Во время ввода кастомной формулы preview в overlay и Active Algorithm показывают draft-формулу до сохранения.
- Удалять можно только пользовательские алгоритмы; встроенные варианты остаются защищенными.

### 6. Статусы обучения

Статусы хранятся в локальном профиле и помогают отделять новые кейсы от тех, которые уже закреплены.

- NEW означает, что кейс еще не прорабатывался системно.
- IN_PROGRESS удобно использовать для текущих приоритетов и ежедневной тренировки.
- LEARNED подходит для кейсов, которые уже закреплены, но остаются в каталоге для периодической проверки.
- Статус можно менять как в карточке каталога, так и в панели деталей кейса.

### 7. Экспорт и импорт профиля

Профиль содержит прогресс, выбранные алгоритмы и пользовательские варианты; его можно переносить между устройствами как код.

- Экспорт открывает модал и формирует Base64URL payload, готовый к копированию.
- Импорт ожидает тот же payload и сливает его с текущим профилем без ручного редактирования storage.
- После успешного импорта UI сразу перестраивается под обновленный профиль.
- Этот механизм полезен для синхронизации между desktop и mobile браузером.

### 8. Горячие клавиши и deep links

Несколько клавиш и URL-режимов ускоряют навигацию, тестирование и демонстрацию интерфейса.

- `Space` запускает или ставит на паузу проигрывание.
- `ArrowLeft` и `ArrowRight` двигают timeline по шагам, `R` возвращает в начало.
- `?` открывает manual, `Esc` закрывает manual, settings sheet или profile modal.
- `#manual` открывает справку напрямую, а `#manual/<section-id>` ведет сразу к конкретному разделу.

## EN

### 1. What This Trainer Is

Rubik Motion Trainer combines a case catalog, a 3D algorithm player, and learning controls in one adaptive interface.

- Desktop and mobile are no longer separate interfaces: the trainer now uses one entrypoint and one screen system.
- The catalog remains the source of case selection, while the detail area handles playback and algorithm inspection.
- Help is available directly inside the trainer through the Help button or the '?' shortcut.

### 2. Adaptive Layout

The interface adapts to the viewport automatically, but you can pin the mode with the `?layout=` query parameter.

- Desktop: the catalog and detail pane are visible at the same time.
- Tablet: both areas stay on screen, but the layout becomes more vertical.
- Mobile: catalog and details switch as separate views, while status and algorithm controls move into the Settings sheet.
- For forced verification use `?layout=desktop`, `?layout=mobile`, or keep `?layout=auto`.

### 3. Working with the Catalog

The catalog shows cases for the selected group and lets you update learning priorities quickly.

- The F2L / OLL / PLL tabs switch the active group without reloading the page.
- Progress Sort reorders cards so in-progress cases appear first.
- Clicking the colored dot cycles the status through NEW -> IN_PROGRESS -> LEARNED.
- Clicking the card itself opens the case details and loads the currently active algorithm into the sandbox.

### 4. Controlling the 3D Player

The sandbox plays the algorithm step by step and lets you inspect the formula as a continuous timeline animation.

- The ⏮, ⏪, ▶, and ⏩ buttons jump to start, move by steps, and start or stop playback.
- The `x1`, `x1.5`, and `x2` buttons change playback tempo without changing the selected algorithm.
- The timeline slider lets you jump to any point inside the sequence.
- The current step is highlighted both in the player and in the Active Algorithm block below the video.

### 5. Selecting and Adding Algorithms

For each case you can switch between bundled algorithms and add your own custom variants.

- The radio control makes the selected algorithm active and immediately reloads the timeline.
- Custom algorithms are entered in the `Enter custom algorithm...` field and applied with the Use button.
- While typing a custom formula, the overlay and Active Algorithm preview show the draft formula before it is saved.
- Only custom algorithms can be deleted; bundled variants stay protected.

### 6. Learning Statuses

Statuses are stored in the local profile and separate new cases from the ones that are already mastered.

- NEW means the case has not been studied in a structured way yet.
- IN_PROGRESS works well for current priorities and daily practice.
- LEARNED is useful for cases that feel stable but should remain in the catalog for periodic review.
- You can change the status either from the catalog card or from the case detail panel.

### 7. Exporting and Importing the Profile

The profile stores progress, selected algorithms, and custom variants; you can move it between devices as a code payload.

- Export opens a modal and generates a Base64URL payload that is ready to copy.
- Import expects the same payload and merges it into the current profile without manual storage edits.
- After a successful import, the UI immediately refreshes against the updated profile.
- This is the main way to sync state between desktop and mobile browsers.

### 8. Shortcuts and Deep Links

A few shortcuts and URL modes make navigation, testing, and demos faster.

- `Space` starts or pauses playback.
- `ArrowLeft` and `ArrowRight` move the timeline by steps, while `R` returns to the start.
- `?` opens the manual, and `Esc` closes the manual, the settings sheet, or the profile modal.
- `#manual` opens the guide directly, and `#manual/<section-id>` jumps to a specific section.
