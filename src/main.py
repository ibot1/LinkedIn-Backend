from aiohttp import ClientSession
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent_map import ConcurrentMap
from typing import Union, Any
import asyncio
import re
import math

_user_ids_per_page = 10
_max_invitations = 100
_concurrent_map: ConcurrentMap[int, Any] = ConcurrentMap()
_Executor = Union[ProcessPoolExecutor, ThreadPoolExecutor]
_user_ids_reg_exp = re.compile(r'<a href="/[a-zA-Z-0-9]+/in/([a-zA-Z-0-9]+)"')
_user_ids_count_reg_exp = re.compile(r">([0-9,]+) results<")

# TODO: handle all exceptions
# TODO: fetch a list of accepted connections and possibly pending ones too
# TODO: linkedin's limits by playing around with the headers specifically the user_agent and ids?
# TODO: Possible optimization for the regexp op maybe by parallel processing by splitting?

_get_headers: dict[str, str] = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "cookie": "PASTE YOUR BROWSER COOKIES",
    "sec-ch-ua": '"Microsoft Edge";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": "Android",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36 Edg/113.0.1774.57",
}

_post_headers_ = lambda user_id: {
    "accept": "*/*",
    "content-type": "application/json",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "cookie": "PASTE YOUR BROWSER COOKIES",
    "csrf-token": "PASTE THIS HEADER TOO",
    "origin": "https://www.linkedin.com",
    "referer": f"https://www.linkedin.com/in/{user_id}?trk=feed_main-feed-card_feed-actor-name",
    "sec-ch-ua": '"Microsoft Edge";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": "Android",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36 Edg/113.0.1774.57",
    "x-effective-connection-type": "3g",
    "x-requested-with": "XMLHttpRequest",
    "x-referer-pagekey": "p_mwlite_profile_view",
    "x-li-page-instance": "PASTE THIS HEADER TOO",
    "x-tracking-id": "PASTE THIS HEADER TOO",
}


async def add_connection_request(client: ClientSession, user_id: str):
    url = "https://www.linkedin.com/mwlite/invite/"
    body = {"inviteeVanityName": user_id, "origin": "p_mwlite_profile_view"}

    async with client.post(url, json=body, headers=_post_headers_(user_id)) as resp:
        return resp.status


async def get_page_count(client: ClientSession, pool: _Executor) -> int:
    return math.ceil((await get_user_ids_count(client, pool)) / _user_ids_per_page)


def _to_int_(input: str) -> int:
    return int(input.replace(",", ""))


def _get_user_ids_count_(data: str) -> int:
    match = _user_ids_count_reg_exp.search(data)
    return _to_int_(match.groups()[0]) if match else 0


async def get_user_ids_count(client: ClientSession, pool: _Executor) -> int:
    url = "https://www.linkedin.com/mwlite/search/results/all?origin=GLOBAL_SEARCH_HEADER&keywords=founders%20canada%20tech"
    data = ""

    async with client.get(url, headers=_get_headers) as resp:
        data = await resp.text()

    return pool.submit(_get_user_ids_count_, data).result()


async def get_user_ids_request(client: ClientSession, pool: _Executor, page_no: int):
    url = f"https://www.linkedin.com/mwlite/search/results/all?keywords=founders+canada+tech&origin=GLOBAL_SEARCH_HEADER&pageNumber={page_no}"

    async with client.get(url, headers=_get_headers) as resp:
        await _concurrent_map.put(
            page_no,
            asyncio.ensure_future(process_user_ids(await resp.text(), page_no, pool)),
        )


async def process_user_ids(resp: str, id: int, pool: _Executor):
    return pool.submit(_process_user_ids_, resp, id)


def _process_user_ids_(resp: str, id: int):
    return set(_user_ids_reg_exp.findall(resp))


async def main() -> None:
    with ProcessPoolExecutor() as pool:
        async with ClientSession() as client:
            page_count = await get_page_count(client, pool)
            async with asyncio.TaskGroup() as task_group:
                for page_no in range(1, page_count + 1):
                    task_group.create_task(get_user_ids_request(client, pool, page_no))


if __name__ == "__main__":
    asyncio.run(main())
