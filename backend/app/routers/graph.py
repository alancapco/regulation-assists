from fastapi import APIRouter, Depends
from neo4j import AsyncDriver

from backend.app import cypher
from backend.app.config import settings
from backend.app.deps import get_driver, graph_params, run
from backend.app.mapping import map_graph
from backend.app.schemas import GraphData, GraphQuery

router = APIRouter()


@router.get("/api/graph")
async def get_graph(
    driver: AsyncDriver = Depends(get_driver),
    params: GraphQuery = Depends(graph_params),
) -> GraphData:
    # 管辖区/主题过滤走 Cypher 内部 EXISTS 子查询；图库断连由 main.py 全局处理器统一转 503，
    # 此处不重捕——复用共享异常处理器，避免重复实现。
    rows = await run(driver, cypher.Q_GRAPH,
                     jurisdiction=params.jurisdiction, topic=params.topic,
                     reg_limit=settings.graph_reg_limit)
    # 100 节点上限、丢悬空边、id 前缀、优先级全在 map_graph 内，本卡只负责调用，不重实现截断。
    return map_graph(rows, max_nodes=settings.graph_max_nodes)
