import argparse
import asyncio
import os
from pathlib import Path

from browser_use import Agent, Browser
from langchain.chat import ChatLangchain
from langchain_openai import ChatOpenAI


async def main(task: str):
	langchain_model = ChatOpenAI(
		model=os.getenv('ELE_LLM_AUTOPILOT_MODEL'),
		api_key=os.getenv('ELE_LLM_API_KEY'),
		base_url=os.getenv('ELE_LLM_BASE_URL'),
		temperature=0.0,
	)
	llm = ChatLangchain(chat=langchain_model)

	chrome_executable_path = os.getenv('CHROME_EXECUTABLE_PATH')
	chrome_user_data_dir = os.getenv('CHROME_USER_DATA_DIR')
	chrome_profile_directory = os.getenv('CHROME_PROFILE_DIRECTORY')

	# storage_state：脚本结束会导出更新（默认写到 ~/.config/browseruse/acq/storage_state.json）
	storage_state_path = Path(
		Path.home() / '.config' / 'browseruse' / 'storage_state.json'
	).expanduser()
	storage_state_path.parent.mkdir(parents=True, exist_ok=True)

	browser = Browser(
		executable_path=chrome_executable_path,
		user_data_dir=chrome_user_data_dir,
		profile_directory=chrome_profile_directory,
		storage_state=str(storage_state_path) if storage_state_path.exists() else None,
		headless=False,
		keep_alive=False,
	)

	agent = Agent(
		task=task,
		llm=llm,
		browser=browser,
	)

	try:
		await agent.run(max_steps=120)
	finally:
		# 导出 cookies/session 到 storage_state，便于后续复用/排查
		try:
			await browser.export_storage_state(storage_state_path)
		except Exception as e:
			print(f'⚠️ 导出 storage_state 失败: {e}')

		# 关闭浏览器，确保程序退出
		await browser.stop()

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--path', required=True, help='Path to task file')
	args = parser.parse_args()

	task_content = Path(args.path).read_text(encoding='utf-8')
	asyncio.run(main(task_content))
