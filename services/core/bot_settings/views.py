from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from common.permissions import StrictDjangoModelPermissions, require_organization

from .models import BotMessages
from .serializers import BotMessagesSerializer


class BotMessagesView(RetrieveUpdateAPIView):
    """Mensajes predeterminados del bot de la organización del usuario
    autenticado — un registro por organización, se crea solo en el primer
    GET. `queryset` es sólo para que `StrictDjangoModelPermissions` sepa de
    qué modelo se trata (GET necesita `view_botmessages`, PATCH necesita
    `change_botmessages`)."""

    queryset = BotMessages.objects.all()
    serializer_class = BotMessagesSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_object(self):
        organization_id = require_organization(self.request)
        obj, _ = BotMessages.objects.get_or_create(organization_id=organization_id)
        return obj
