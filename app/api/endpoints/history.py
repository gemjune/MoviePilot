from pathlib import Path
from typing import List, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.chain.transfer import TransferChain
from app.core.event import eventmanager
from app.core.security import verify_token
from app.db import get_db
from app.db.models.downloadhistory import DownloadHistory
from app.db.models.transferhistory import TransferHistory
from app.schemas import MediaType
from app.schemas.types import EventType

router = APIRouter()


@router.get("/download", summary="查询下载历史记录", response_model=List[schemas.DownloadHistory])
def download_history(page: int = 1,
                     count: int = 30,
                     db: Session = Depends(get_db),
                     _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    查询下载历史记录
    """
    return DownloadHistory.list_by_page(db, page, count)


@router.delete("/download", summary="删除下载历史记录", response_model=schemas.Response)
def delete_download_history(history_in: schemas.DownloadHistory,
                            db: Session = Depends(get_db),
                            _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    删除下载历史记录
    """
    DownloadHistory.delete(db, history_in.id)
    return schemas.Response(success=True)


@router.get("/transfer", summary="查询转移历史记录", response_model=schemas.Response)
def transfer_history(title: str = None,
                     page: int = 1,
                     count: int = 30,
                     db: Session = Depends(get_db),
                     _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    查询转移历史记录
    """
    if title:
        total = TransferHistory.count_by_title(db, title)
        result = TransferHistory.list_by_title(db, title, page, count)
    else:
        result = TransferHistory.list_by_page(db, page, count)
        total = TransferHistory.count(db)

    return schemas.Response(success=True,
                            data={
                                "list": result,
                                "total": total,
                            })


@router.delete("/transfer", summary="删除转移历史记录", response_model=schemas.Response)
def delete_transfer_history(history_in: schemas.TransferHistory,
                            deletesrc: bool = False,
                            deletedest: bool = False,
                            db: Session = Depends(get_db),
                            _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    删除转移历史记录
    """
    history = TransferHistory.get(db, history_in.id)
    if not history:
        return schemas.Response(success=False, msg="记录不存在")
    # 册除媒体库文件
    if deletedest and history.dest:
        TransferChain(db).delete_files(Path(history.dest))
    # 删除源文件
    if deletesrc and history.src:
        TransferChain(db).delete_files(Path(history.src))
        # 发送事件
        eventmanager.send_event(
            EventType.DownloadFileDeleted,
            {
                "src": history.src
            }
        )
    # 删除记录
    TransferHistory.delete(db, history_in.id)
    return schemas.Response(success=True)


@router.post("/transfer", summary="历史记录重新转移", response_model=schemas.Response)
def redo_transfer_history(history_in: schemas.TransferHistory,
                          mtype: str = None,
                          new_tmdbid: int = None,
                          db: Session = Depends(get_db),
                          _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    历史记录重新转移，不输入 mtype 和 new_tmdbid 时，自动使用文件名重新识别
    """
    if mtype and new_tmdbid:
        state, errmsg = TransferChain(db).re_transfer(logid=history_in.id,
                                                      mtype=MediaType(mtype), tmdbid=new_tmdbid)
    else:
        state, errmsg = TransferChain(db).re_transfer(logid=history_in.id)
    if state:
        return schemas.Response(success=True)
    else:
        return schemas.Response(success=False, message=errmsg)
