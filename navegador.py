from playwright.async_api import async_playwright, Playwright, Browser, Page, BrowserContext
import asyncio
import os

# Directorio raíz donde Playwright guardará temporalmente los archivos.
TEMP_DOWNLOAD_ROOT = "temp_endesa_downloads" 

class NavegadorAsync:
    """
    Clase que encapsula la inicialización, uso y cierre de una sesión 
    de Playwright Asíncrona.
    """
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.context: BrowserContext | None = None
        
        # Aseguramos que el directorio exista
        os.makedirs(TEMP_DOWNLOAD_ROOT, exist_ok=True)

    async def iniciar(self):
        """Inicializa la sesión de Playwright y lanza el navegador."""
        self.playwright = await async_playwright().start()
        
        # Mantenemos headless=True para el servidor
        self.browser = await self.playwright.chromium.launch(headless=False) 
        
        # --- CAMBIOS PARA EVITAR BLOQUEOS Y MEJORAR ESTABILIDAD ---
        self.context = await self.browser.new_context(
            # 1. User Agent real (Chrome en Windows 10)
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            # 2. Resolución de pantalla estándar
            viewport={'width': 1920, 'height': 1080},
            # 3. Idioma aceptado (evita que la web cargue versiones raras)
            extra_http_headers={
                "Accept-Language": "es-ES,es;q=0.9"
            },
            accept_downloads=True
        )
        self.page = await self.context.new_page()
        
        return self 

    async def goto_url(self, url: str, timeout_ms: int = 60000) -> Page:
        """Navega a la URL especificada."""
        await self.page.goto(
            url, 
            wait_until="networkidle", # Cambiado de domcontentloaded a networkidle
            timeout=timeout_ms
        ) 
        return self.page

    async def cerrar(self):
        """Cierra el navegador y detiene el contexto."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    def get_page(self) -> Page:
        """Devuelve el objeto Page actual."""
        if not self.page:
            raise RuntimeError("El navegador no ha sido inicializado.")
        return self.page