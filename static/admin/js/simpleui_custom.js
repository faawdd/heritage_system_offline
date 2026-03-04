(function () {
    function hasCookie(name) {
        return document.cookie.split(';').some(function (cookie) {
            return cookie.trim().indexOf(name + '=') === 0;
        });
    }

    function setFontSizeCookie(px) {
        document.cookie = 'fontSize=' + px + '; path=/';
    }

    if (hasCookie('fontSize')) {
        return;
    }

    var defaultSize = 14;
    if (window.screen && window.screen.width > 1920) {
        defaultSize = 16;
    }

    setFontSizeCookie(defaultSize);
})();
