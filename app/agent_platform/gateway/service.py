import time
from app.agent_platform.schemas import UnifiedChatRequest, UnifiedChatResponse
from app.agent_platform.gateway.resolvers import Resolvers
from app.agent_platform.gateway.factory import ProviderFactory
from app.agent_platform.gateway.tracker import Tracker

class AIGatewayService:
    """
    The orchestrator for the Universal AI Gateway.
    Resolves configs, invokes the LLM, tracks usage, and returns a unified response.
    """
    
    @staticmethod
    async def process_request(request: UnifiedChatRequest) -> UnifiedChatResponse:
        start_time = time.time()
        
        # 1. Resolve Company Config (Validate tenant)
        company_config = Resolvers.get_company_config(request.company_id)
        if not company_config.get("is_active"):
            raise PermissionError("Company account is not active.")

        # 2. Resolve Provider Config (Get API Key)
        provider_config = Resolvers.get_provider_config(request.company_id, request.provider)

        # 3. Resolve Model Config (Get Pricing)
        model_config = Resolvers.get_model_config(request.company_id, request.provider, request.model)

        # 4. Instantiate Provider via Factory
        provider_instance = ProviderFactory.get_provider(request.provider, provider_config)

        # 5. Execute API Call
        response = await provider_instance.generate_response(request)

        # 6. Calculate Latency and Cost
        latency = time.time() - start_time
        response.latency = latency
        
        estimated_cost = Tracker.calculate_cost(
            input_tokens=response.input_tokens, 
            output_tokens=response.output_tokens, 
            model_config=model_config
        )
        response.estimated_cost = estimated_cost

        # 7. Log Usage Async
        Tracker.log_usage(
            company_id=request.company_id,
            agent_id=request.agent_id,
            provider=request.provider,
            model=request.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_cost=estimated_cost
        )

        return response
