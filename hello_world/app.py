import json
import os
import requests
import traceback  # 追加
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain.schema import HumanMessage
from langchain.prompts import PromptTemplate

class WeatherTool:
    def __init__(self):
        self.area_data = self._get_area_data()
        self.center_codes = {
            "佐賀県": "400000"  # 佐賀地方気象台のコード
        }
        
    def _get_area_data(self):
        """気象庁APIから地域情報を取得"""
        try:
            response = requests.get('https://www.jma.go.jp/bosai/common/const/area.json')
            response.raise_for_status()  # エラーチェック
            return response.json()
        except Exception as e:
            print(f"地域情報の取得に失敗: {str(e)}")
            return {}

    def _get_area_code(self, city_name):
        """市町村名から気象庁のエリアコードを取得"""
        print(f"検索する地域名: {city_name}")
        
        # 県名での直接マッピング
        if (city_name in self.center_codes):
            return self.center_codes[city_name]
            
        # 都道府県での検索
        for code, data in self.area_data.get('offices', {}).items():
            if city_name in data.get('name', ''):
                print(f"都道府県コードが見つかりました: {code}")
                return code

        # 市町村での検索
        for code, data in self.area_data.get('class10s', {}).items():  # class20sからclass10sに変更
            if city_name in data.get('name', ''):
                print(f"市町村コードが見つかりました: {code}")
                return code
                
        return "400000"  # デフォルトで佐賀地方気象台のコードを返す

    @tool("get_weather")
    def get_weather(self, city: str = "佐賀市") -> str:
        """指定された地域の天気情報を取得します"""
        try:
            area_code = self._get_area_code(city)
            print(f"使用する地域コード: {area_code}")

            # 天気予報APIのエンドポイント
            forecast_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
            print(f"APIリクエストURL: {forecast_url}")
            
            response = requests.get(forecast_url)
            response.raise_for_status()
            weather_data = response.json()
            
            print(f"取得した天気データ: {json.dumps(weather_data, ensure_ascii=False, indent=2)}")
            
            # 天気情報の抽出（インデックスとキーを修正）
            area_weather = weather_data[0]['timeSeries'][0]['areas'][0]
            area_temp = weather_data[0]['timeSeries'][2]['areas'][0]
            
            weather = area_weather.get('weather', '不明')
            temp = area_temp.get('temp', ['--'])[0]
            
            return f"""
            {city}の天気情報:
            天気: {weather}
            気温: {temp}℃
            """
            
        except Exception as e:
            stack_trace = traceback.format_exc()  # スタックトレースを文字列として取得
            print(f"天気情報の取得エラー: {str(e)}")
            print(f"スタックトレース:\n{stack_trace}")
            return f"天気情報の取得に失敗しました。詳細: {str(e)}"

def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """
    api_key = os.environ.get('GOOGLE_API_KEY')
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)
    
    # ツールの設定
    weather_tool = WeatherTool()
    tools = [Tool(
        name="WeatherTool",
        func=weather_tool.get_weather,
        description="佐賀の天気情報を取得するツール"
    )]

    # Agentの設定
    prompt = PromptTemplate(
        template="""あなたは天気情報のアシスタントです。
        
        以下のツールが利用可能です:
        {tools}

        以下のツール名が利用可能です:
        {tool_names}

        あなたは必ず天気情報を取得するためにWeatherToolを使用してください。
        市町村名が指定された場合はその名前をそのまま使用し、
        県名が指定された場合は県庁所在地の天気を取得してください。

        ユーザーからの質問に答えるために以下のフォーマットを使用してください:
        Question: 入力された質問
        Thought: 問題を解決するために何をすべきか考えます
        Action: WeatherTool
        Action Input: 地域名
        Observation: ツールからの結果
        Thought: これで十分な情報が得られました
        Final Answer: 最終的な回答

        始めましょう！

        Question: {input}
        {agent_scratchpad}""",
        input_variables=["tools", "tool_names", "input", "agent_scratchpad"]
    )
    
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    try:
        message = event.get('message', '{}')
        if not message:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Message is required in request body"
                })
            }
        
        # Agentを実行
        response = agent_executor.invoke({"input": message})
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json; charset=utf-8"
            },
            "body": json.dumps({
                "message": message,
                "response": response['output']
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }
