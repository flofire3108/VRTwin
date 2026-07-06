"""History-limited conversation memory.

AIAvatarKit fetches up to 100 past messages per reply. In a public VRChat room
that is one shared, ever-growing conversation, which inflates token cost and
mixes different players together. This caps the memory to the most recent
`max_messages` and otherwise reuses AIAvatarKit's SQLite storage.
"""

from typing import List, Dict, Union

from aiavatar.sts.llm.context_manager import SQLiteContextManager


class LimitedSQLiteContextManager(SQLiteContextManager):
    def __init__(self, db_path="aiavatar.db", context_timeout=3600, max_messages=30):
        super().__init__(db_path=db_path, context_timeout=context_timeout)
        self.max_messages = max_messages

    async def get_histories(
        self,
        context_id: Union[str, List[str]],
        limit: int = 100,
        include_timestamp: bool = False,
    ) -> List[Dict]:
        return await super().get_histories(
            context_id=context_id,
            limit=min(limit, self.max_messages),
            include_timestamp=include_timestamp,
        )
