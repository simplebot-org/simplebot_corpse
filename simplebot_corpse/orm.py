from contextlib import contextmanager
from threading import Lock

from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import relationship, sessionmaker


class Base:
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


Base = declarative_base(cls=Base)
_Session = sessionmaker()
_lock = Lock()


class Game(Base):
    chat_id = Column(Integer, primary_key=True)
    text = Column(String, default="", nullable=False)
    turn = Column(String(500))
    rounds = Column(Integer, default=3, nullable=False)
    words = Column(Integer, default=10, nullable=False)

    players = relationship(
        "Player", backref="game", cascade="all, delete, delete-orphan"
    )

    def __init__(self, **kwargs) -> None:
        if "rounds" not in kwargs:
            kwargs["rounds"] = 3
        if "words" not in kwargs:
            kwargs["words"] = 10
        if "text" not in kwargs:
            kwargs["text"] = ""
        super().__init__(**kwargs)


class Player(Base):
    addr = Column(String(500), primary_key=True)
    chat_id = Column(Integer, ForeignKey("game.chat_id"), nullable=False)
    round = Column(Integer, default=1, nullable=False)

    def __init__(self, **kwargs) -> None:
        if "round" not in kwargs:
            kwargs["round"] = 1
        super().__init__(**kwargs)


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    with _lock:
        session = _Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()


def init(path: str, debug: bool = False) -> None:
    """Initialize engine."""
    engine = create_engine(path, echo=debug)
    Base.metadata.create_all(engine)
    _Session.configure(bind=engine)
