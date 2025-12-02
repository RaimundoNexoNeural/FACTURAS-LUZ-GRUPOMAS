from navegador import NavegadorAsync # Importamos la clase base del navegador
import asyncio
from playwright.async_api import Page, TimeoutError # Importamos Page para tipado y TimeoutError para manejo de errores

# --- CONSTANTES DE ENDESA ---

# Usamos la URL que confirmaste en tu prueba manual
URL_LOGIN = "https://endesa-atenea.my.site.com/miempresa/s/login/?language=es" 

# Credenciales REALES proporcionadas por el usuario
USER = "pfombellav@somosgrupomas.com" 
PASSWORD = "Guillena2024*" 

# URL base de éxito. La URL de destino DEBE empezar por aquí y NO contener 'login'.
URL_SUCCESS_ROOT = "https://endesa-atenea.my.site.com/miempresa/s/" 



async def _iniciar_sesion(page: Page, username: str, password: str) -> bool:
    """
    Función interna para manejar la lógica de autenticación en Endesa.
    
    Rellena el formulario usando los selectores basados en el HTML proporcionado.
    """
    print(f"Intentando iniciar sesión con usuario: {username}")
    
    try:
        # Esperamos a que el formulario de login esté visible
        await page.wait_for_selector('form.slds-form', timeout=10000)

        # 1. Rellenar campo de usuario: Usamos el atributo 'name'
        await page.fill('input[name="Username"]', username)
        
        # 2. Rellenar campo de contraseña: Usamos el atributo 'name'
        await page.fill('input[name="password"]', password)
        
        # 3. Hacer click en el botón de iniciar sesión
        login_button_selector = 'button:has-text("ACCEDER")'
        
        # Ejecutamos el click. Esto inicia el proceso de redirección.
        await page.click(login_button_selector)
        
        # 4. Esperar la redirección y verificación Post-Login.
        # CRÍTICO: Cambiamos 'networkidle' por 'domcontentloaded' para reducir la probabilidad de Timeout
        await page.wait_for_url(
            lambda url: url.startswith(URL_SUCCESS_ROOT) and "login" not in url.lower(), 
            timeout=30000, 
            wait_until="domcontentloaded" # Condición menos estricta
        )
        
        # 5. Verificación Final: Si la ejecución llega aquí, la redirección ocurrió.
        is_successful = not "login" in page.url.lower()
        
        if is_successful:
            print(f"Login exitoso. URL actual: {page.url}")
            return True
        else:
            print(f"Fallo en la verificación de URL. La URL final es: {page.url}")
            return False

    except TimeoutError:
        final_url = page.url
        print("Fallo en el Login: El tiempo de espera para la redirección ha expirado.")
        # Comprobación de si hay un mensaje de error visible
        error_message_selector = 'div[class*="error"], span[class*="error"], p:has-text("credenciales")'
        if final_url.startswith(URL_LOGIN) and await page.is_visible(error_message_selector):
             print("Razón: Credenciales incorrectas. La página de login persiste con un error visible.")
        elif final_url.startswith(URL_LOGIN):
             print("Razón: Fallo en la redirección. La página de login persiste.")
        return False
    
    except Exception as e:
        print(f"Error inesperado durante la autenticación: {e}")
        return False

async def _aceptar_cookies(page: Page):
    """
    Función interna para aceptar el banner de cookies si está presente.
    Usamos un timeout corto ya que es un elemento que aparece al inicio.
    """
    cookie_button_selector = '#truste-consent-button'
    
    try:
        # Espera un máximo de 5 segundos a que el botón sea visible
        await page.wait_for_selector(cookie_button_selector, timeout=5000)
        
        # Si el selector se encuentra, hacemos clic
        await page.click(cookie_button_selector)
        print("Cookies aceptadas.")
        
        # Opcional: Esperar un momento a que el banner desaparezca
        await page.wait_for_timeout(500) 
        
    except TimeoutError:
        # Si el botón no aparece en 5 segundos, asumimos que no hay banner de cookies o ya fue aceptado.
        print("Banner de cookies no detectado o ya aceptado. Continuando...")
        pass

    except Exception as e:
        print(f"Error al intentar aceptar las cookies: {e}")



async def ejecutar_prueba_acceso() -> bool:
    """
    Función principal para la prueba de acceso e inicio de sesión en el portal de Endesa.
    """
    robot = NavegadorAsync()
    login_successful = False
    
    try:
        # 1. Iniciar el navegador y obtener la página
        await robot.iniciar()
        page = robot.get_page()

        # 2. Navegar a la página de inicio de sesión de Endesa
        print(f"Navegando a la URL: {URL_LOGIN}")
        await robot.goto_url(URL_LOGIN)
        
        # 3. Intentar el inicio de sesión
        login_successful = await _iniciar_sesion(page, USER, PASSWORD)
        
        # 4. Si el login es exitoso, manejar las cookies
        if login_successful:
            await _aceptar_cookies(page)
        
        # 5. Mostrar el resultado de la prueba
        if login_successful:
            print("Resultado de la prueba: ✅ INICIO DE SESIÓN COMPLETO Y EXITOSO.")
            # Esperar para observación visual si el login es exitoso
            await page.wait_for_timeout(5000) 
        else:
            print("Resultado de la prueba: ❌ FALLO EN EL INICIO DE SESIÓN.")
            # Esperar para observación visual si hay un fallo
            await page.wait_for_timeout(5000) 
        
        return login_successful

    except Exception as e:
        print(f"Ocurrió un error inesperado durante el proceso de prueba: {e}")
        return False
    
    finally:
        input("Presiona ENTER para cerrar el navegador y finalizar la prueba...")
        # 6. Cerrar el navegador
        await robot.cerrar()
        print("Sesión de navegador cerrada.")






# --- FUNCIÓN DE PRUEBA Y EJECUCIÓN MANUAL ---
if __name__ == "__main__":

    print("--- INICIO DE PRUEBA MANUAL DEL ROBOT ENDESA (ACCESO Y LOGIN) ---")
    
    try:
        # Ejecutamos la función principal asíncrona
        asyncio.run(ejecutar_prueba_acceso())

    except KeyboardInterrupt:
        print("\nEjecución manual interrumpida por el usuario.")


    print("--- FIN DE PRUEBA MANUAL ---")