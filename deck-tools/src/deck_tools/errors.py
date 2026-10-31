"""Material-reader errors local to this package."""


class SourceUnreadable(Exception):
    exit_code = 2

    def __init__(self, path, detail):
        self.detail = detail
        super().__init__(f"读取材料失败：{path}；{detail}；请检查文件后重试")


class SourceUnsupported(SourceUnreadable):
    pass


class SourceNeedsTool(SourceUnreadable):
    exit_code = 3
