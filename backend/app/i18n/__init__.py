# Translation messages for backend

messages = {
    'en': {
        # Auth messages
        'session_required': 'Session required',
        'invalid_session': 'Invalid session',
        'admin_required': 'Admin access required',
        'unauthorized': 'Unauthorized access',
        
        # Container messages
        'container_not_found': 'Container not found',
        'container_stopped': 'Container stopped successfully',
        'container_removed': 'Container removed successfully',
        'containers_stopped': 'Successfully stopped {count} container(s)',
        'containers_removed': 'Successfully removed {count} stopped container(s)',
        'failed_to_stop_container': 'Failed to stop container',
        'failed_to_remove_container': 'Failed to remove container',
        'failed_to_start_container': 'Failed to start container',
        'container_already_running': 'Container is already running',
        
        # Desktop types
        'desktop_type_not_found': 'Desktop type not found',
        'desktop_type_exists': 'Desktop type with this name already exists',
        'name_and_image_required': 'Name and docker_image are required',
        'desktop_type_created': 'Desktop type created successfully',
        'desktop_type_updated': 'Desktop type updated successfully',
        'desktop_type_deleted': 'Desktop type deleted successfully',
        
        # File operations
        'no_file_provided': 'No file provided',
        'no_file_selected': 'No file selected',
        'invalid_file_type': 'Invalid file type. Allowed: {types}',
        'file_too_large': 'File too large. Maximum size is {size}',
        'file_uploaded': 'File uploaded successfully',
        'file_deleted': 'File deleted successfully',
        'folder_created': 'Folder created successfully',
        'failed_to_upload': 'Failed to upload file',
        'failed_to_delete': 'Failed to delete file',
        'failed_to_create_folder': 'Failed to create folder',
        
        # Assignment messages
        'assignment_created': 'Assignment created successfully',
        'assignment_updated': 'Assignment updated successfully',
        'assignment_deleted': 'Assignment deleted successfully',
        'assignment_not_found': 'Assignment not found',
        'assignment_exists': 'Assignment already exists',
        'group_or_user_required': 'Either group_id or user_id is required',
        'desktop_types_required': 'No desktop types specified',
        
        # Theme messages
        'theme_saved': 'Theme saved successfully',
        'theme_loaded': 'Theme loaded successfully',
        'failed_to_save_theme': 'Failed to save theme',
        'failed_to_load_theme': 'Failed to load theme',
        
        # General errors
        'error_occurred': 'An error occurred',
        'invalid_request': 'Invalid request',
        'internal_error': 'Internal server error',
        'not_found': 'Resource not found',
    },
    'de': {
        # Auth messages
        'session_required': 'Sitzung erforderlich',
        'invalid_session': 'Ungültige Sitzung',
        'admin_required': 'Admin-Zugriff erforderlich',
        'unauthorized': 'Nicht autorisierter Zugriff',
        
        # Container messages
        'container_not_found': 'Container nicht gefunden',
        'container_stopped': 'Container erfolgreich gestoppt',
        'container_removed': 'Container erfolgreich entfernt',
        'containers_stopped': '{count} Container erfolgreich gestoppt',
        'containers_removed': '{count} gestoppte Container erfolgreich entfernt',
        'failed_to_stop_container': 'Container konnte nicht gestoppt werden',
        'failed_to_remove_container': 'Container konnte nicht entfernt werden',
        'failed_to_start_container': 'Container konnte nicht gestartet werden',
        'container_already_running': 'Container läuft bereits',
        
        # Desktop types
        'desktop_type_not_found': 'Desktop-Typ nicht gefunden',
        'desktop_type_exists': 'Desktop-Typ mit diesem Namen existiert bereits',
        'name_and_image_required': 'Name und Docker-Image sind erforderlich',
        'desktop_type_created': 'Desktop-Typ erfolgreich erstellt',
        'desktop_type_updated': 'Desktop-Typ erfolgreich aktualisiert',
        'desktop_type_deleted': 'Desktop-Typ erfolgreich gelöscht',
        
        # File operations
        'no_file_provided': 'Keine Datei bereitgestellt',
        'no_file_selected': 'Keine Datei ausgewählt',
        'invalid_file_type': 'Ungültiger Dateityp. Erlaubt: {types}',
        'file_too_large': 'Datei zu groß. Maximale Größe ist {size}',
        'file_uploaded': 'Datei erfolgreich hochgeladen',
        'file_deleted': 'Datei erfolgreich gelöscht',
        'folder_created': 'Ordner erfolgreich erstellt',
        'failed_to_upload': 'Hochladen fehlgeschlagen',
        'failed_to_delete': 'Löschen fehlgeschlagen',
        'failed_to_create_folder': 'Ordner konnte nicht erstellt werden',
        
        # Assignment messages
        'assignment_created': 'Zuweisung erfolgreich erstellt',
        'assignment_updated': 'Zuweisung erfolgreich aktualisiert',
        'assignment_deleted': 'Zuweisung erfolgreich gelöscht',
        'assignment_not_found': 'Zuweisung nicht gefunden',
        'assignment_exists': 'Zuweisung existiert bereits',
        'group_or_user_required': 'Gruppe oder Benutzer erforderlich',
        'desktop_types_required': 'Keine Desktop-Typen angegeben',
        
        # Theme messages
        'theme_saved': 'Design erfolgreich gespeichert',
        'theme_loaded': 'Design erfolgreich geladen',
        'failed_to_save_theme': 'Design konnte nicht gespeichert werden',
        'failed_to_load_theme': 'Design konnte nicht geladen werden',
        
        # General errors
        'error_occurred': 'Ein Fehler ist aufgetreten',
        'invalid_request': 'Ungültige Anfrage',
        'internal_error': 'Interner Serverfehler',
        'not_found': 'Ressource nicht gefunden',
    }
}


def get_message(key: str, lang: str = 'en', **kwargs) -> str:
    """
    Get a translated message.
    
    Args:
        key: Message key
        lang: Language code ('en' or 'de')
        **kwargs: Format parameters for the message
    
    Returns:
        Translated message with parameters substituted
    """
    lang = lang if lang in messages else 'en'
    message = messages.get(lang, {}).get(key, messages['en'].get(key, key))
    
    # Replace format parameters
    if kwargs:
        try:
            message = message.format(**kwargs)
        except (KeyError, ValueError):
            pass
    
    return message


def get_language_from_request():
    """
    Get language preference from request.
    Checks Accept-Language header and defaults to English.
    
    Returns:
        Language code ('en' or 'de')
    """
    from flask import request
    
    # Check for explicit language parameter
    lang = request.args.get('lang') or request.headers.get('X-Language')
    if lang in ('en', 'de'):
        return lang
    
    # Check Accept-Language header
    accept_language = request.headers.get('Accept-Language', '')
    if 'de' in accept_language.lower():
        return 'de'
    
    return 'en'
