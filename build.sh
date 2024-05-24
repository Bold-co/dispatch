export EMAIL=$USERNAME@boldcf.co

export image=dispatch
export dest_tag=dispatch_v$(date +%Y%m%d)

export ROLE=arn:aws:iam::215297755614:role/ProductionSharedIAM-AdminC75D2A91-J3FPLPIFA359
export AWS_PROFILE=prod_shared
export region=us-east-1

export TIME=3590
#aws-google-auth --save-failure-html -u $EMAIL -I C049pw73t -S 313831081126 \
#  -d $TIME -R us-east-1 -p $AWS_PROFILE --bg-response  js_enabled \
#  -r $ROLE #-k

docker build . -f Dockerfile2 -t image -t 215297755614.dkr.ecr.us-east-1.amazonaws.com/bold:$dest_tag
aws ecr get-login-password --region $region | docker login --username AWS --password-stdin 215297755614.dkr.ecr.$region.amazonaws.com
docker push 215297755614.dkr.ecr.us-east-1.amazonaws.com/bold:$dest_tag
