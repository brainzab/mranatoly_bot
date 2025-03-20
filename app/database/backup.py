import os
import asyncio
import logging
import datetime
from app.config import BACKUP_PATH
from app.services.monitoring import monitoring

logger = logging.getLogger(__name__)

async def backup_database(database_url, backup_path=BACKUP_PATH):
    """
    Создаёт резервную копию базы данных в виде SQL дампа
    """
    try:
        # Создаем директорию для бэкапов если её нет
        os.makedirs(backup_path, exist_ok=True)
        
        # Формируем имя файла бэкапа с датой
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_path, f"backup_{timestamp}.sql")
        
        # Извлекаем параметры подключения из URL
        conn_params = database_url.replace("postgresql://", "").split("@")
        user_pass = conn_params[0].split(":")
        host_db = conn_params[1].split("/")
        
        username = user_pass[0]
        password = user_pass[1] if len(user_pass) > 1 else ""
        host = host_db[0].split(":")[0]  # Отделяем порт, если он есть
        database = host_db[1].split("?")[0]  # Отбрасываем параметры
        
        # Подготавливаем команду для pg_dump
        cmd = f"PGPASSWORD={password} pg_dump -h {host} -U {username} -d {database} > {backup_file}"
        
        logger.info(f"Запуск резервного копирования в файл {backup_file}")
        
        # Выполняем команду
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info(f"Резервная копия БД успешно создана: {backup_file}")
            # Уведомляем мониторинг
            await monitoring.notify_admin(f"✅ Резервная копия базы данных создана: {backup_file}")
            return backup_file
        else:
            logger.error(f"Ошибка создания бэкапа: {stderr.decode()}")
            # Уведомляем мониторинг об ошибке
            await monitoring.notify_admin(f"❌ Ошибка создания резервной копии: {stderr.decode()}")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка в процессе создания резервной копии: {e}")
        await monitoring.notify_admin(f"❌ Ошибка создания резервной копии: {e}")
        return None