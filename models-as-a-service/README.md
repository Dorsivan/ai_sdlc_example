To list api-keys, you need to weirdly run a post request, actually 

`curl -X POST http://a61320ff97c734ff49798c5d76421dd0-2008927439.us-east-1.elb.amazonaws.com/maas-api/v1/api-keys/search -H "Authorization: Bearer <some_maas_api_key>" -d {}`

Generating a key goes like this:

curl -X POST http://a61320ff97c734ff49798c5d76421dd0-2008927439.us-east-1.elb.amazonaws.com/maas-api/v1/api-keys -H "Authorization: Bearer <some_openshift_token>" -H "Content-Type: application/json" -d '{ "name": "fools-key", "subscription":"gpt-oss-20b-subscription", "expiresInDays": 9 }'
