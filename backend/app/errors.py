from backend.app.schemas import ErrorDetail, ErrorEnvelope

# 冻结错误码 -> (HTTP status, 默认 message)；全局异常处理器与各 router 共用
ERRORS: dict[str, tuple[int, str]] = {
    "VALIDATION_ERROR":   (400, "参数校验失败"),
    "NOT_FOUND":          (404, "未找到该法规"),
    "NEO4J_UNAVAILABLE":  (503, "无法连接到图数据库，请检查 Neo4j 服务状态"),
    "INTERNAL_ERROR":     (500, "服务器内部错误"),
}


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail

    def envelope(self) -> ErrorEnvelope:
        return ErrorEnvelope(error=ErrorDetail(
            code=self.code, message=self.message, detail=self.detail))


def envelope(code: str, message: str | None = None, detail: str | None = None) -> tuple[int, ErrorEnvelope]:
    status, default = ERRORS[code]
    return status, ErrorEnvelope(error=ErrorDetail(
        code=code, message=message or default, detail=detail))
