!macro customUnInstall
  ${ifNot} ${isUpdated}
    SetShellVarContext current
    !ifdef APP_FILENAME
      RMDir /r "$APPDATA\${APP_FILENAME}"
    !endif
    !ifdef APP_PRODUCT_FILENAME
      RMDir /r "$APPDATA\${APP_PRODUCT_FILENAME}"
    !endif
    !ifdef APP_PACKAGE_NAME
      RMDir /r "$APPDATA\${APP_PACKAGE_NAME}"
      RMDir /r "$LOCALAPPDATA\${APP_PACKAGE_NAME}"
    !endif
    RMDir /r "$PROFILE\.heritage-system"
  ${endIf}
!macroend