from django.utils import translation


class AdminLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            translation.activate("ru")
            request.LANGUAGE_CODE = "ru"
        return self.get_response(request)