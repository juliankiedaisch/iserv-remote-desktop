# Translation messages for backend

messages = {
    'en': {
        # Auth messages
        'session_required': 'Session required',
        'no_session_id_provided': 'No session ID provided',
        'invalid_session': 'Invalid session',
        'session_expired': 'Session expired',
        'session_expired_refresh_failed': 'Session expired and refresh failed',
        'admin_required': 'Admin access required',
        'teacher_required': 'Teacher or admin role required',
        'unauthorized': 'Unauthorized access',
        'successfully_logged_out': 'Successfully logged out',
        'logout_error': 'Error during logout: {error}',
        
        # Container messages
        'container_not_found': 'Container not found',
        'container_stopped': 'Container stopped successfully',
        'container_removed': 'Container removed successfully',
        'container_started': 'Container started successfully',
        'container_queued': 'Container creation queued (position: {queue_position})',
        'containers_stopped': 'Successfully stopped {count} container(s)',
        'containers_removed': 'Successfully removed {count} stopped container(s)',
        'failed_to_stop_container': 'Failed to stop container',
        'failed_to_remove_container': 'Failed to remove container',
        'failed_to_start_container': 'Failed to start container',
        'container_already_running': 'Container already running',
        'no_container': 'No container for this session',
        'no_running_container': 'No running container found',
        'desktop_type_disabled': 'Desktop type "{desktop_type}" is currently disabled',
        'no_desktop_permission': 'You do not have permission to access "{desktop_type}" desktops',
        'desktop_type_param_required': 'desktop_type parameter required',
        'container_not_running': 'Container not found or not running',
        
        # Desktop types
        'desktop_type_not_found': 'Desktop type not found',
        'desktop_type_exists': 'Desktop type with this name already exists',
        'name_and_image_required': 'Name and docker_image are required',
        'desktop_type_created': 'Desktop type created successfully',
        'desktop_type_updated': 'Desktop type updated successfully',
        'desktop_type_deleted': 'Desktop type deleted successfully',
        'desktop_image_id_required': 'desktop_image_id is required',
        'invalid_file_type_allowed': 'Invalid file type. Allowed: {types}',
        'file_size_exceeded': 'File too large. Maximum size is 2MB',
        
        # File operations
        'no_file_provided': 'No file provided',
        'no_file_selected': 'No file selected',
        'invalid_file_type': 'Invalid file type. Allowed: {types}',
        'file_too_large': 'File too large. Maximum size is {size}',
        'file_uploaded': 'File uploaded successfully',
        'file_deleted': 'Deleted successfully',
        'folder_created': 'Folder created successfully',
        'failed_to_upload': 'Failed to upload file',
        'failed_to_delete': 'Failed to delete file',
        'failed_to_create_folder': 'Failed to create folder',
        'invalid_path': 'Invalid path: outside allowed directory',
        'directory_not_found': 'Directory not found',
        'no_file_path_provided': 'No file path provided',
        'file_not_found': 'File not found',
        'path_not_file': 'Path is not a file',
        'cannot_delete_base_directory': 'Cannot delete base directory',
        'file_or_directory_not_found': 'File or directory not found',
        'no_folder_name_provided': 'No folder name provided',
        'invalid_folder_name': 'Invalid folder name',
        'folder_already_exists': 'Folder already exists',
        'invalid_filename': 'Invalid filename',
        'upload_directory_not_exist': 'Upload directory does not exist. Please create it first.',
        'source_dest_paths_required': 'Source and destination paths are required',
        'source_not_found': 'Source file or directory not found',
        'dest_must_be_directory': 'Destination must be a directory',
        'cannot_move_into_itself': 'Cannot move a folder into itself',
        'item_exists_in_dest': 'A file or folder named "{name}" already exists in the destination',
        'moved_successfully': 'Moved successfully',
        'moved_and_updated_assignments': 'Moved successfully and updated {count} assignment(s)',
        
        # Assignment messages
        'assignment_created': 'Assignment created successfully',
        'assignment_updated': 'Assignment updated successfully',
        'assignment_deleted': 'Assignment deleted successfully',
        'assignment_not_found': 'Assignment not found',
        'assignment_exists': 'Assignment already exists',
        'group_or_user_required': 'Either group_id or user_id is required',
        'at_least_one_group_or_user': 'At least one group or user is required',
        'desktop_types_required': 'No desktop types specified',
        'group_not_found': 'Group not found',
        'invalid_folder_path': 'Invalid folder path',
        'folder_not_exist': 'Selected folder does not exist',
        
        # Theme messages
        'theme_saved': 'Theme saved successfully',
        'theme_loaded': 'Theme loaded successfully',
        'failed_to_save_theme': 'Failed to save theme',
        'failed_to_load_theme': 'Failed to load theme',
        'theme_settings_required': 'Theme settings are required',
        'theme_data_required': 'Theme data is required',
        'favicon_data_required': 'Favicon data is required',
        'invalid_favicon_format': 'Invalid favicon format. Must be a base64 encoded image.',
        'favicon_size_exceeded': 'Favicon size exceeds 1MB limit',
        
        # User management messages
        'user_not_found': 'User not found',
        'user_role_updated': 'User role updated successfully',
        
        # General errors
        'error_occurred': 'An error occurred',
        'invalid_request': 'Invalid request',
        'internal_error': 'Internal server error',
        'not_found': 'Resource not found',
    },
    'de': {
        # Auth messages
        'session_required': 'Sitzung erforderlich',
        'no_session_id_provided': 'Keine Sitzungs-ID angegeben',
        'invalid_session': 'Ungültige Sitzung',
        'session_expired': 'Sitzung abgelaufen',
        'session_expired_refresh_failed': 'Sitzung abgelaufen und Aktualisierung fehlgeschlagen',
        'admin_required': 'Admin-Zugriff erforderlich',
        'teacher_required': 'Lehrer- oder Admin-Rolle erforderlich',
        'unauthorized': 'Nicht autorisierter Zugriff',
        'successfully_logged_out': 'Erfolgreich abgemeldet',
        'logout_error': 'Fehler beim Abmelden: {error}',
        
        # Container messages
        'container_not_found': 'Container nicht gefunden',
        'container_stopped': 'Container erfolgreich gestoppt',
        'container_removed': 'Container erfolgreich entfernt',
        'container_started': 'Container erfolgreich gestartet',
        'container_queued': 'Container-Erstellung in Warteschlange (Position: {queue_position})',
        'containers_stopped': '{count} Container erfolgreich gestoppt',
        'containers_removed': '{count} gestoppte Container erfolgreich entfernt',
        'failed_to_stop_container': 'Container konnte nicht gestoppt werden',
        'failed_to_remove_container': 'Container konnte nicht entfernt werden',
        'failed_to_start_container': 'Container konnte nicht gestartet werden',
        'container_already_running': 'Container läuft bereits',
        'no_container': 'Kein Container für diese Sitzung',
        'no_running_container': 'Kein laufender Container gefunden',
        'desktop_type_disabled': 'Desktop-Typ "{desktop_type}" ist derzeit deaktiviert',
        'no_desktop_permission': 'Sie haben keine Berechtigung für "{desktop_type}"-Desktops',
        'desktop_type_param_required': 'desktop_type-Parameter erforderlich',
        'container_not_running': 'Container nicht gefunden oder läuft nicht',
        
        # Desktop types
        'desktop_type_not_found': 'Desktop-Typ nicht gefunden',
        'desktop_type_exists': 'Desktop-Typ mit diesem Namen existiert bereits',
        'name_and_image_required': 'Name und Docker-Image sind erforderlich',
        'desktop_type_created': 'Desktop-Typ erfolgreich erstellt',
        'desktop_type_updated': 'Desktop-Typ erfolgreich aktualisiert',
        'desktop_type_deleted': 'Desktop-Typ erfolgreich gelöscht',
        'desktop_image_id_required': 'desktop_image_id ist erforderlich',
        'invalid_file_type_allowed': 'Ungültiger Dateityp. Erlaubt: {types}',
        'file_size_exceeded': 'Datei zu groß. Maximale Größe ist 2MB',
        
        # File operations
        'no_file_provided': 'Keine Datei bereitgestellt',
        'no_file_selected': 'Keine Datei ausgewählt',
        'invalid_file_type': 'Ungültiger Dateityp. Erlaubt: {types}',
        'file_too_large': 'Datei zu groß. Maximale Größe ist {size}',
        'file_uploaded': 'Datei erfolgreich hochgeladen',
        'file_deleted': 'Erfolgreich gelöscht',
        'folder_created': 'Ordner erfolgreich erstellt',
        'failed_to_upload': 'Hochladen fehlgeschlagen',
        'failed_to_delete': 'Löschen fehlgeschlagen',
        'failed_to_create_folder': 'Ordner konnte nicht erstellt werden',
        'invalid_path': 'Ungültiger Pfad: außerhalb des erlaubten Verzeichnisses',
        'directory_not_found': 'Verzeichnis nicht gefunden',
        'no_file_path_provided': 'Kein Dateipfad angegeben',
        'file_not_found': 'Datei nicht gefunden',
        'path_not_file': 'Pfad ist keine Datei',
        'cannot_delete_base_directory': 'Basisverzeichnis kann nicht gelöscht werden',
        'file_or_directory_not_found': 'Datei oder Verzeichnis nicht gefunden',
        'no_folder_name_provided': 'Kein Ordnername angegeben',
        'invalid_folder_name': 'Ungültiger Ordnername',
        'folder_already_exists': 'Ordner existiert bereits',
        'invalid_filename': 'Ungültiger Dateiname',
        'upload_directory_not_exist': 'Upload-Verzeichnis existiert nicht. Bitte erstellen Sie es zuerst.',
        'source_dest_paths_required': 'Quell- und Zielpfade sind erforderlich',
        'source_not_found': 'Quelldatei oder -verzeichnis nicht gefunden',
        'dest_must_be_directory': 'Ziel muss ein Verzeichnis sein',
        'cannot_move_into_itself': 'Ein Ordner kann nicht in sich selbst verschoben werden',
        'item_exists_in_dest': 'Eine Datei oder ein Ordner namens "{name}" existiert bereits im Ziel',
        'moved_successfully': 'Erfolgreich verschoben',
        'moved_and_updated_assignments': 'Erfolgreich verschoben und {count} Zuweisung(en) aktualisiert',
        
        # Assignment messages
        'assignment_created': 'Zuweisung erfolgreich erstellt',
        'assignment_updated': 'Zuweisung erfolgreich aktualisiert',
        'assignment_deleted': 'Zuweisung erfolgreich gelöscht',
        'assignment_not_found': 'Zuweisung nicht gefunden',
        'assignment_exists': 'Zuweisung existiert bereits',
        'group_or_user_required': 'Gruppe oder Benutzer erforderlich',
        'at_least_one_group_or_user': 'Mindestens eine Gruppe oder ein Benutzer erforderlich',
        'desktop_types_required': 'Keine Desktop-Typen angegeben',
        'group_not_found': 'Gruppe nicht gefunden',
        'invalid_folder_path': 'Ungültiger Ordnerpfad',
        'folder_not_exist': 'Ausgewählter Ordner existiert nicht',
        
        # Theme messages
        'theme_saved': 'Design erfolgreich gespeichert',
        'theme_loaded': 'Design erfolgreich geladen',
        'failed_to_save_theme': 'Design konnte nicht gespeichert werden',
        'failed_to_load_theme': 'Design konnte nicht geladen werden',
        'theme_settings_required': 'Design-Einstellungen sind erforderlich',
        'theme_data_required': 'Design-Daten sind erforderlich',
        'favicon_data_required': 'Favicon-Daten sind erforderlich',
        'invalid_favicon_format': 'Ungültiges Favicon-Format. Muss ein base64-codiertes Bild sein.',
        'favicon_size_exceeded': 'Favicon-Größe überschreitet 1MB-Limit',
        
        # User management messages
        'user_not_found': 'Benutzer nicht gefunden',
        'user_role_updated': 'Benutzerrolle erfolgreich aktualisiert',
        
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
