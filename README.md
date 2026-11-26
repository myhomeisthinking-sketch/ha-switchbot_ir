# SwitchBot IR

[日本語](#日本語) | [English](#english)

---

# 日本語

SwitchBot の**クラウドAPI**を使い、ハブに登録した**赤外線リモコン**のボタンを、Home Assistant の**ボタンエンティティ**として登録・管理するカスタムインテグレーションです（赤外線リモコンのみが対象です）。

HA標準の `switchbot_cloud` 統合とは別に動作します。

## 特長

- SwitchBotアプリで登録した赤外線リモコンの一覧を取得し、`button.switchbot_...` として登録
- SwitchBotアプリで学習させたボタン（カスタムボタン）と、標準コマンド（`turnOn` など）の、両方に対応
- 標準コマンドの一覧画面（リモコンの種類別）を内蔵
- サイドバーの専用パネル（管理者のみ）で、登録・編集・削除
- クラウドへの問い合わせは、「情報を取得」を押したときだけ
- 削除するとき、そのボタンを参照している設定を一覧表示
- ボタンは、リモコンごとのデバイスにまとまります
- エリアの指定に対応

## 前提

- SwitchBot のトークンとシークレット（SwitchBotアプリ：プロフィール → 設定 → アプリバージョンを10回タップ → 開発者向けオプション）
- SwitchBot ハブに、赤外線リモコンが登録されていること
- インターネットへの接続（クラウドAPIを使います）

## 動作確認環境

- インストール方法：Home Assistant OS
- Home Assistant Core：2026.11.2
- Supervisor：2026.11.0
- Operating System：18.4
- フロントエンド：20261028.6

## インストール

### HACS（カスタムリポジトリ）

1. HACS を開き、右上のメニューから「カスタムリポジトリ」を選びます。
2. リポジトリに `https://github.com/myhomeisthinking-sketch/ha-switchbot_ir` を、種類に「Integration」を指定して追加します。
3. HACS で「SwitchBot IR」をダウンロードし、HAを再起動します。
4. 設定 → デバイスとサービス → 統合を追加 →「SwitchBot IR」を選びます。
5. サイドバーに「SwitchBot IR」（管理者のみ）が表示されます。

### 手動

1. `custom_components/switchbot_ir/` を、HAの `config/custom_components/` にコピーします。
2. HAを再起動します。
3. 設定 → デバイスとサービス → 統合を追加 →「SwitchBot IR」を選びます。
4. サイドバーに「SwitchBot IR」（管理者のみ）が表示されます。

## 使い方

1. **トークンとシークレットの設定**：「SwitchBot クラウド」の「設定」に入力します。保存前に、クラウドで有効かどうかを確認します。リセットしたときも、ここから入れ替えます（片方だけの変更もできます）。
2. **情報を取得**：「情報を取得」を押すと、赤外線リモコンの一覧を取得します。結果は保存され、再起動後も残ります。
3. **ボタンを登録**：リモコンを選び、**種別**と**ボタン名**を入力します。種別を変えても、画面の並びは同じです（リモコン → 種別 → ボタン名 → テスト送信 → エンティティID → アクション名称 → アイコン・エリア）。
   - **カスタムボタン**：ボタン名に、SwitchBotアプリで学習させたボタンの名前を、そのまま入力します（DIY・Othersタイプの既定）。
   - **標準コマンド**：ボタン名に、`turnOn`・`turnOff`・`setAll` などの標準のコマンド名を入力します。パラメータ欄が出ます（エアコンの `setAll` は `26,2,3,on` の形）。ボタン名の下の「こちら」から、リモコンの種類ごとの**標準コマンド一覧**が開きます。「使う」を押すと、コマンド名がボタン名の欄に、パラメータの例があれば、パラメータの欄にも入ります（出典：SwitchBot API 公式ドキュメント）。
   - どちらの種別でも、ボタン名は `command` として送信され、アクション名称がボタンの名称になります（標準コマンドのコマンド名を、表示名には使いません）。
   - 「テスト送信」で、実際に送って確認できます。カスタムボタンのテスト送信に失敗しても、SwitchBotアプリで操作できるボタンなら、種別を標準コマンドに変更して試してください。
   - 続けて、`button.switchbot_` の後ろのID、アクション名称（カスタムボタンでは、ボタン名を入れると「リモコン名 ボタン名」が自動で入ります）、アイコン・エリア（任意）を入力して追加します。
4. **登録済みのボタン**：送信 / 編集（名称・アイコン・エリア・リモコン・種別・ボタン名・パラメータ） / 削除ができます。削除するときは、そのボタンを参照している設定を表示し、ボタンのエンティティも、あわせて削除します。

同じボタンを、すでに登録している場合は、追加できません。

## ボタンとして使う

登録したボタンは、ダッシュボードに置いたり、automation や script から押したりできます。

```yaml
- action: button.press
  target:
    entity_id: button.switchbot_tv_power
```

- エンティティIDは、登録時に指定したものになります。後から変更するときは、HAの「設定 → デバイスとサービス → エンティティ」で行ってください（登録内容は内部の識別子で管理しているため、影響しません）。
- エリアは、ボタンのエンティティのエリアとして設定されます。HAの画面で変更した場合も、パネルは現在のエリアを表示します。パネルの編集で、解除もできます。
- `button.press` は、値を渡せません。実行のたびにパラメータを変える場合（エアコンの温度など）は、`switchbot_ir.send` サービスを直接呼んでください。
- 複数の操作を続けて行う場合は、script や automation の中で `button.press` を順に呼びます。

## サービス

- `switchbot_ir.send`（`device_id`、`command`、`command_type`、`parameter`）：赤外線リモコンのボタン（コマンド）を送信します。`command_type` は、`customize`（カスタムボタン）または `command`（標準コマンド）です。

## 注意

- SwitchBot API v1.1 の署名認証（トークン + 時刻 + nonce を、シークレットでHMAC-SHA256）で通信します。
- 呼び出しは、1日10,000回までです。パネルに、この統合の本日の呼び出し回数を表示します（他のアプリやスクリプトの分は含みません）。認証エラー（401）は、上限を超えたときにも返ります。
- APIがエラーを返したときは、ステータスコードとメッセージをパネルに表示し、151・152・160・161・171・190 には、対処のヒントも添えます。
- 赤外線リモコンの状態は取得できないため、送信が成功しても、機器が実際に動いたかどうかは、APIでは分かりません。
- トークン・シークレット・取得した一覧・登録内容は、統合の保存領域（`.storage/switchbot_ir`）に保存されます。
- 削除時の参照検索は、automations.yaml / scenes.yaml / scripts.yaml / configuration.yaml / ダッシュボード（Lovelace）の保存データが対象です。ダッシュボードのカードなど、検出できない場所もあります。

## セキュリティ

- パネルとAPIは、管理者のみが使えます（サーバー側でも、管理者かどうかを確認します）。
- トークンとシークレットは、`.storage/switchbot_ir` に、所有者だけが読める権限で保存されます。HAのバックアップにも含まれるので、バックアップは、秘匿情報として扱ってください。トークンとシークレットを、画面・ログ・APIの応答に出すことはありません。
- クラウドとの通信は、証明書を検証するHTTPSです。トークン・シークレットの形式（空白・改行を含まない、8〜512文字の半角）を検証し、ヘッダーに入れる値も、検査してから送ります。
- クラウドから受け取った名称などは、制御文字を除き、長さを制限して保存し、画面に表示する値は、すべてエスケープします。
- サービス（`switchbot_ir.send`）は、HAの権限の仕組みに従い、管理者以外のユーザーからも呼び出せます。

## ライセンス

MIT License です。詳細は、[LICENSE](LICENSE) を参照してください。

同梱のアイコン・ロゴ画像（`custom_components/.../brand/`）には、SwitchBot の商標が含まれます。これらの画像は、MITライセンスの対象外です。

## 免責事項

本プロジェクトは、SwitchBot の提供元とは無関係の、非公式なものです。「SwitchBot」は、その提供元の商標です。

---

# English

This custom integration uses the **SwitchBot Cloud API** to register and manage buttons from **infrared remote controls** configured on SwitchBot Hubs as **button entities** in Home Assistant. Only infrared remote controls are supported.

It operates independently of Home Assistant's built-in `switchbot_cloud` integration.

## Features

- Retrieves the list of infrared remote controls registered in the SwitchBot app and registers their buttons as `button.switchbot_...` entities.
- Supports both custom buttons learned through the SwitchBot app and standard commands such as `turnOn`.
- Includes a built-in reference listing standard commands by remote control type.
- Provides a dedicated sidebar panel (administrators only) for adding, editing, and deleting buttons.
- Communicates with the cloud only when **Fetch Information** is pressed.
- Displays a list of configurations that reference a button before deleting it.
- Groups buttons into devices based on their associated remote controls.
- Supports area assignment.

## Requirements

- SwitchBot API Token and Secret (SwitchBot app: Profile → Settings → tap App Version 10 times → Developer Options).
- At least one infrared remote control registered on a SwitchBot Hub.
- Internet connection (uses the cloud API).

## Tested Environment

- Installation method: Home Assistant OS
- Home Assistant Core: 2026.11.2
- Supervisor: 2026.11.0
- Operating System: 18.4
- Frontend: 20261028.6

## Installation

### HACS (Custom Repository)

1. Open HACS and select **Custom repositories** from the menu in the upper-right corner.
2. Add `https://github.com/myhomeisthinking-sketch/ha-switchbot_ir` as a repository and select **Integration** as the category.
3. Download **SwitchBot IR** through HACS and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and select **SwitchBot IR**.
5. **SwitchBot IR** will appear in the sidebar (administrators only).

### Manual Installation

1. Copy `custom_components/switchbot_ir/` into `config/custom_components/` in your Home Assistant configuration directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and select **SwitchBot IR**.
4. **SwitchBot IR** will appear in the sidebar (administrators only).

## Usage

1. **Set Token and Secret**: Enter your Token and Secret under **Settings** in the **SwitchBot Cloud** section. Both are validated against the cloud before being saved. You can replace them here after resetting them. You can also update either one independently.
2. **Fetch Information**: Press **Fetch Information** to retrieve the list of infrared remote controls. The results are saved and persist across restarts.
3. **Register a Button**: Select a remote control and enter the **Type** and **Button Name**. The layout of the form remains the same regardless of the selected type (Remote Control → Type → Button Name → Test Send → Entity ID → Action Name → Icon / Area).
   - **Custom Button**: Enter the button name exactly as it appears in the SwitchBot app. This is the default for DIY and Others remote control types.
   - **Standard Command**: Enter a standard command name such as `turnOn`, `turnOff`, or `setAll` in the Button Name field. A parameter field will appear. For example, the `setAll` command for an air conditioner uses the format `26,2,3,on`. Select **here** below the Button Name field to open the **Standard Command List** for the selected remote control type. Press **Use** to populate the command name and, if an example parameter is available, the parameter field as well. (Source: Official SwitchBot API documentation.)
   - For both types, the Button Name is sent as the `command` value, while the Action Name is used as the button's display name. Standard command names are not used as display names.
   - Use **Test Send** to send the command and verify that it works. If testing a custom button fails, but the button works in the SwitchBot app, try changing the type to Standard Command.
   - Finally, enter an ID after `button.switchbot_`, an Action Name, and optionally an Icon and Area. For custom buttons, entering the button name automatically populates the Action Name with `Remote Control Name Button Name`.
4. **Manage Registered Buttons**: You can send commands, edit buttons (change the name, icon, area, remote control, type, button name, or parameter), and delete buttons. Before deletion, the integration displays a list of configurations referencing the button and also removes the corresponding button entity.

A button that has already been registered cannot be added again.

## Using Buttons

Registered buttons can be added to dashboards or pressed from automations and scripts.

```yaml
- action: button.press
  target:
    entity_id: button.switchbot_tv_power
```

- The entity ID is the one specified during registration. To change it later, use **Settings → Devices & Services → Entities** in Home Assistant. This does not affect the integration's internal management, as registered items are identified using internal identifiers.
- The assigned area is set as the button entity's area. If you change the area through the Home Assistant interface, the panel will display the currently assigned area. You can also clear the area through the panel's edit function.
- `button.press` does not accept parameters. If you need to change parameters each time you execute a command (for example, the temperature of an air conditioner), call the `switchbot_ir.send` service directly.
- To perform multiple operations in sequence, call `button.press` for each button in a script or automation.

## Services

- `switchbot_ir.send` (`device_id`, `command`, `command_type`, `parameter`): Sends a button command to an infrared remote control. `command_type` must be either `customize` (custom button) or `command` (standard command).

## Notes

- Communication uses SwitchBot API v1.1 signature authentication (Token + timestamp + nonce, signed with HMAC-SHA256 using the Secret).
- The API allows up to 10,000 calls per day. The panel displays the number of calls made by this integration today (calls made by other apps or scripts are not included). An authentication error (401) may also be returned when the daily limit is exceeded.
- When the API returns an error, the panel displays the status code and message. For error codes 151, 152, 160, 161, 171, and 190, additional troubleshooting hints are provided.
- The state of infrared remote-controlled devices cannot be retrieved. Therefore, even if a command is successfully sent, the API cannot confirm whether the target device actually operated.
- The Token, Secret, retrieved remote control list, and registered button configurations are stored in the integration's storage directory (`.storage/switchbot_ir`).
- Reference checks performed before deletion cover `automations.yaml`, `scenes.yaml`, `scripts.yaml`, `configuration.yaml`, and saved dashboard (Lovelace) data. Some references, such as those in dashboard cards, may not be detected.

## Security

- The panel and its API are accessible to administrators only. Administrator privileges are also verified on the server side.
- The Token and Secret are stored in `.storage/switchbot_ir` with permissions that allow only their owner to read them. They are also included in Home Assistant backups, so backups should be treated as confidential. The Token and Secret are never exposed in the UI, logs, or API responses.
- Communication with the cloud uses HTTPS with certificate verification. The Token and Secret formats (8–512 ASCII characters, without spaces or line breaks) are validated, and values are checked before being included in request headers.
- Names and other data received from the cloud have control characters removed and their lengths restricted before storage. All values displayed in the UI are properly escaped.
- The service (`switchbot_ir.send`) follows Home Assistant's permission system and can also be called by non-administrator users.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

The bundled icon and logo images (`custom_components/.../brand/`) contain SwitchBot trademarks. These images are not covered by the MIT License.

## Disclaimer

This is an unofficial project and is not affiliated with the provider of SwitchBot. "SwitchBot" is a trademark of its respective owner.