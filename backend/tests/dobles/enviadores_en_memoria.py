"""Dobles de los puertos EnviadorCorreo y EnviadorPush (MATU-41): guardan lo enviado y responden lo que la
prueba programa (ENVIADO por omisión). Nunca envían nada."""

from dataclasses import dataclass, field

from app.modules.notifications.application.ports import EnvioCorreo, EnvioPush
from app.modules.notifications.domain.aviso import ResultadoEnvio


@dataclass
class EnviadorCorreoEnMemoria:
    # Una respuesta por llamada, en orden; cuando se acaban, ENVIADO
    respuestas: list[ResultadoEnvio] = field(default_factory=list)
    enviados: list[EnvioCorreo] = field(default_factory=list)

    def enviar(self, envio: EnvioCorreo) -> ResultadoEnvio:
        self.enviados.append(envio)
        return self.respuestas.pop(0) if self.respuestas else ResultadoEnvio.ENVIADO


@dataclass
class EnviadorPushEnMemoria:
    # Respuesta fija por push_token; los demás tokens, `respuesta`
    por_token: dict[str, ResultadoEnvio] = field(default_factory=dict)
    respuesta: ResultadoEnvio = ResultadoEnvio.ENVIADO
    enviados: list[EnvioPush] = field(default_factory=list)

    def enviar(self, envio: EnvioPush) -> ResultadoEnvio:
        self.enviados.append(envio)
        return self.por_token.get(envio.push_token, self.respuesta)
