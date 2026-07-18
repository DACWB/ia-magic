# 🎥 Integração com OBS Studio

Como capturar imagens do Arena via OBS de forma mais rápida e estável.

## 📋 Setup no OBS

### 1. Verificar OBS Studio
```
Versão: 30.0+ (recomendado)
Como verificar: OBS → Help → About
Download: https://obsproject.com
```

### 2. Habilitar WebSocket
```
OBS → Tools → WebSocket Server Settings
✅ Enable WebSocket server
Server Port: 4455 (default)
Enable authentication: Sim (por segurança)
Password: [criar uma forte, ex: MagicAI_Advisor_2026!]
```

### 3. Configurar Cena
```
Sources:
├─ Game Capture 1903 (MTG Arena)
│  ├─ Mode: Capture specific window
│  ├─ Window: MTG Arena
│  └─ Capture Cursor: Sim
```

### 4. Verificar Resolução
```
OBS → Settings → Video
Base (Canvas): 1920x1080
Output (Scaled): 1920x1080 (mesmo)
Common FPS: 60 fps
```

## 🐍 Conexão Python

### Instalação
```bash
pip install obswebsocket-py
# ou versão mais nova:
pip install obs-websocket-py
```

### Código base (test connection)
```python
# test_obs_connection.py
from obswebsocket import obsws, requests

# Conectar ao OBS
ws = obsws("localhost", 4455, "MagicAI_Advisor_2026!")
ws.connect()

# Testar
print("✅ Conectado ao OBS")

# Listar cenas
scenes = ws.call(requests.GetSceneList())
print(f"Cenas disponíveis: {[s['sceneName'] for s in scenes.getScenes()]}")

# Pegar screenshot
screenshot = ws.call(requests.GetSourceScreenshot(
    sourceName="Game Capture 1903",
    imageFormat="png",
    imageWidth=1920,
    imageHeight=1080
))

# screenshot.getImageData() = base64 do PNG

ws.disconnect()
```

### Loop de captura contínua
```python
# obs_capture_loop.py
import asyncio
import base64
from obswebsocket import obsws, requests
from datetime import datetime

class OBSCaptureService:
    def __init__(self, host="localhost", port=4455, password="..."):
        self.host = host
        self.port = port
        self.password = password
        self.ws = None
        self.source_name = "Game Capture 1903"
        self.frame_count = 0
    
    async def connect(self):
        """Conecta ao OBS via WebSocket"""
        self.ws = obsws(self.host, self.port, self.password)
        self.ws.connect()
        print("✅ Conectado ao OBS WebSocket")
    
    async def get_screenshot(self, width=1280, height=720) -> bytes:
        """
        Pega screenshot da cena atual.
        Retorna PNG em bytes.
        """
        try:
            screenshot = self.ws.call(requests.GetSourceScreenshot(
                sourceName=self.source_name,
                imageFormat="png",
                imageWidth=width,
                imageHeight=height,
                imageCompressionQuality=75  # 75% pra ser mais rápido
            ))
            
            # image_data vem como base64 data URL
            # "data:image/png;base64,iVBORw0KG..."
            data_url = screenshot.getImageData()
            _, encoded = data_url.split(",", 1)
            return base64.b64decode(encoded)
        
        except Exception as e:
            print(f"❌ Erro capturing: {e}")
            return None
    
    async def capture_loop(self, interval_ms=100):
        """
        Loop de captura contínua.
        interval_ms = intervalo entre frames (100ms = 10 FPS)
        """
        while True:
            try:
                start = datetime.now()
                
                # Pega screenshot
                image_bytes = await self.get_screenshot()
                
                if image_bytes:
                    self.frame_count += 1
                    yield image_bytes
                
                # Ajusta intervalo pra ficar preciso
                elapsed_ms = (datetime.now() - start).total_seconds() * 1000
                sleep_time = max(0, interval_ms - elapsed_ms) / 1000
                await asyncio.sleep(sleep_time)
                
                # Log FPS a cada 30 frames
                if self.frame_count % 30 == 0:
                    print(f"📊 Frames capturados: {self.frame_count}")
            
            except KeyboardInterrupt:
                print("\n🛑 Loop parado")
                break
    
    async def disconnect(self):
        """Desconecta do OBS"""
        if self.ws:
            self.ws.disconnect()
            print("✅ Desconectado do OBS")


# Uso
async def main():
    obs = OBSCaptureService(password="MagicAI_Advisor_2026!")
    await obs.connect()
    
    try:
        async for frame_bytes in obs.capture_loop(interval_ms=200):
            # Processa cada frame
            print(f"📸 Frame recebido: {len(frame_bytes)} bytes")
            
            # Salva pra debug (opcional)
            # with open(f"debug_{i}.png", "wb") as f:
            #     f.write(frame_bytes)
    finally:
        await obs.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## ⚡ Otimizações

### 1. Reduzir resolução
```python
# 1920x1080 = grande, mas mais precisão OCR
# 1280x720 = boa relação qualidade/velocidade
# 960x540 = rápido, mas texto ilegível

# RECOMENDADO: 1280x720
```

### 2. Só capturar quando fase muda
```python
# Não precisa 60 FPS, precisa capturar quando ALGO acontece
# Sistema já detecta mudanças, então intervalo pode ser 300-500ms
```

### 3. Compressão JPEG (se necessário)
```python
# PNG é melhor pra texto (cartas)
# Mas JPEG é 5-10x menor
# Trade-off: qualidade vs tamanho
```

## 🐛 Troubleshooting

### Erro: "Connection refused"
```
Solução:
1. Abrir OBS
2. Tools → WebSocket Server Settings
3. Verificar se está enabled
4. Verificar porta (default: 4455)
```

### Erro: "Authentication failed"
```
Solução:
1. Password errada no código
2. Copiar do OBS: Tools → WebSocket → Show Password
3. Passar exatamente igual
```

### Screenshot vem vazio ou preto
```
Possíveis causas:
1. Game Capture 1903 não está ativo
2. Arena não está sendo capturado
3. Mudou o nome do source (deve ser "Game Capture 1903")

Solução:
- Testar screenshot manual no OBS (F12)
- Se vier preto, config do Game Capture está errada
```

### FPS baixo (< 10)
```
Causas:
1. OBS gastando muito CPU pra encoder
2. Resolução muito alta
3. Interval_ms muito baixo

Solução:
1. Reduzir Output resolution pra 1280x720
2. Interval_ms = 300 (3 FPS já é suficiente)
3. Desabilitar codecs pesados
```

## 🎯 Alternativa: Screenshot Direto (sem OBS)

Se OBS travar ou der problema, sistema pode usar `mss` diretamente:

```python
# fallback_direct_capture.py
import mss
import mss.tools

def capture_arena_window():
    with mss.mss() as sct:
        # Área da tela onde está o Arena
        # Você precisa ajustar coordenadas
        monitor = {
            "top": 0,
            "left": 0,
            "width": 1920,
            "height": 1080
        }
        
        screenshot = sct.grab(monitor)
        return mss.tools.to_png(screenshot.rgb, screenshot.size)
```

**Vantagem**: sem OBS, mais rápido
**Desvantagem**: precisa saber posição exata da janela

## 🎯 Recomendação Final

**Comece com OBS + WebSocket** porque:
1. Você já usa OBS
2. Setup simples
3. Se der problema, fallback pra `mss` direto

**Interval de captura**: 200-300ms (3-5 FPS) é suficiente
- Menos que isso: performance ok
- Mais que isso: muita latência de rede

## 📊 Latência Esperada

```
Frame no OBS → Screenshot → Python:  ~50ms
Diff detection:                       ~10ms
OCR Claude Vision:                    ~500ms
Recomendação Claude Sonnet:           ~800ms
Terminal update:                      ~10ms
─────────────────────────────────────────────
TOTAL:                                ~1.4s
```

Objetivo: manter < 2s pra recomendação parecer fluída.
