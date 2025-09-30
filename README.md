# MusicVideo_ProduXer

An **automatic MV (Music Video) generation project** that integrates multiple models, capable of providing end-to-end MV generation starting from lyrics or lyric descriptions.
It also supports mid-process monitoring and iterative optimization.

---

## ⚙️ Environment Setup

1. Create a virtual environment with **Python 3.10** using `venv` or `conda`.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

---

## 🎞 Preparing Your `shots.json` File

To ensure stable execution, your `shots.json` must follow this structure:

```json
{
  "character_description": "A stunningly handsome Chinese man in his late 20s, with sharp yet gentle facial features, pale flawless skin, and profound dark eyes. He has long black hair partially tied up in a loose bun at the back of his head, with several strands falling naturally around his face. He wears elegant ink-wash gradient linen robes in shades of charcoal gray and off-white, with flowing brushstroke patterns. The robes feature wide sleeves that billow in the wind. The overall aesthetic is ethereal, combining traditional Chinese elements with modern xianxia fantasy style. Full body shot, cinematic lighting, soft morning light, highly detailed, photorealistic, 8K resolution.",
  "shots": [
    {
      "id": 0,
      "lyric": "(Intro)",
      "stable": "Wide cinematic shot, Chinese ink-wash style mountains. Morning mist drapes like silk ribbons around green peaks. Water reflects the sky, ultra-low saturation, serene atmosphere.",
      "dynamic": "The camera slowly pushes forward through the mist, gliding silently as the fog flows gently.",
      "duration": 4,
      "sing": false,
      "character": false
    },
    {
      "id": 35,
      "lyric": "The morning mist brushes past the mountain’s shoulder",
      "stable": "Medium shot. The protagonist’s silhouette stands atop a mountain, facing the sea of clouds. Morning light outlines his figure. Black mid-length hair tied into a bun, dressed in ink-wash gradient linen robes, with a thin, wide-sleeved outer robe fluttering slightly.",
      "dynamic": "The camera slowly circles from the protagonist’s side to behind, while the clouds in the background accelerate, visually ‘brushing past’ the mountain.",
      "duration": 11,
      "sing": false,
      "character": true
    }
  ]
}
```

### Key Fields

* **`character_description`**: A detailed description of the MV’s main character.

  * Used by **Seedream 4.0** to generate global character reference images.
  * Refer to [Volcengine Prompt Guide](https://www.volcengine.com/docs/82379/1829186) for tips.

* **`shots`**: A list of detailed shot descriptions.

  * `id`: Shot ID, should be ordered chronologically.
  * `lyric`: The lyric line for this shot.
  * `stable`: Static prompt.
  * `dynamic`: Dynamic prompt.
  * `duration`: Duration of the shot in seconds.
  * `sing`: Whether the character is singing. If `true`, **wan2.1 + Multitalk** will be used for lip-sync.
  * `character`: Whether the character appears in the shot.

    * If `false`: The shot is generated directly via static + dynamic prompts using [Hailuo text-to-video](https://hailuoai.com/create/text-to-video).
    * If `true`: The first frame is generated from the static prompt + character reference, then passed to [Hailuo image-to-video](https://hailuoai.com/create/image-to-video) for full video generation.

---

## 🔑 Get Your API Keys

This project relies on:

* [MiniMax](https://platform.minimaxi.com/)
* [Volcengine](https://www.volcengine.com/)

1. Obtain your API keys.
2. Create a `.env` file in the project root:

   ```bash
   touch .env
   ```
3. Add the following to `.env`:

   ```env
   ARK_API_KEY='your_volcengine_api_key'
   MINIMAX_API_KEY='your_minimax_api_key'
   ```

---

## 🖥 Run the UI

Start the program with:

```bash
python main.py
```