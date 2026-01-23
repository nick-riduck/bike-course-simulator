# PHP Source (Original)

> Exported from `pasted.txt` (uploaded in this chat).

```php
<?php
/**
 * ============================================================================
 * Cycling Power/Speed Simulation API
 * ============================================================================
 * 
 * 사이클링 파워-속도 시뮬레이션 API
 * 물리 법칙 기반으로 파워↔속도 변환, CdA 추정, PR 예측 등을 수행
 * 
 * @endpoint    /json-api/get-simulation.php
 * @method      GET, POST
 * @auth        JWT 인증 필요 (riduck-api-common.php에서 처리)
 * @response    JSON
 * 
 * ============================================================================
 */

/*******************************************************************************
 * SECTION 1: 의존성 및 초기화
 * - riduck-api-common.php: JWT 인증, WordPress 환경, XSS 필터, $user_id 제공
 * - power_curve_model.php: W/kg 기반 파워 커브 모델 데이터
 ******************************************************************************/
include_once("../riduck-api-common.php");
include_once("./power_curve_model.php");

header("Content-type:application/json");

$json = null;    // API 응답 데이터를 담을 배열
$params = null;  // 시뮬레이션 입력 파라미터를 담을 배열

/*******************************************************************************
 * SECTION 2: 요청 파라미터 파싱
 * 모든 입력값은 xssClean()으로 XSS 공격 방지 처리됨
 ******************************************************************************/

// 사용자 인증 관련 (레거시 - 현재는 JWT 사용)
//$title, $config_json, $result_json, $user
$user = xssClean(trim(isset($_REQUEST['user']) ? $_REQUEST['user'] : 0));
$token = xssClean(trim(isset($_REQUEST['token']) ? $_REQUEST['token'] : 0));
$updateConfig = xssClean(trim(isset($_REQUEST['updateConfig']) ? $_REQUEST['updateConfig'] : 0));

// ── 라이더 정보 ──
$params['time_stamp'] = isset($_REQUEST['time_stamp']) ? xssClean(trim($_REQUEST['time_stamp'])) : 0;
$params['gender'] = isset($_REQUEST['gender']) ? xssClean(trim($_REQUEST['gender'])) : "M";           // 성별: M(남), F(여)
$params['rider_height'] = isset($_REQUEST['rider_height']) ? xssClean(trim($_REQUEST['rider_height'])) : 170;  // 키 (cm)
$params['rider_weight'] = isset($_REQUEST['rider_weight']) ? xssClean(trim($_REQUEST['rider_weight'])) : 60;   // 체중 (kg)

// ── 자전거 정보 ──
$params['bike_type'] = isset($_REQUEST['bike_type']) ? xssClean(trim($_REQUEST['bike_type'])) : 'road_allround';  // 자전거 유형
$params['bike_weight'] = isset($_REQUEST['bike_weight']) ? xssClean(trim($_REQUEST['bike_weight'])) : 8.0;        // 자전거 무게 (kg)

// ── 주행 환경 ──
$params['distance'] = isset($_REQUEST['distance']) ? xssClean(trim($_REQUEST['distance'])) : 0;        // 거리 (km)
$params['elevation'] = isset($_REQUEST['elevation']) ? xssClean(trim($_REQUEST['elevation'])) : 0;      // 획득 고도 (m)
$params['altitude'] = isset($_REQUEST['altitude']) ? xssClean(trim($_REQUEST['altitude'])) : 0;         // 평균 고도 (m) - 공기밀도 계산용
$params['temperature'] = isset($_REQUEST['temperature']) ? xssClean(trim($_REQUEST['temperature'])) : 20; // 온도 (°C) - 공기밀도 계산용

// ── 저항 계수 ──
$params['crr'] = isset($_REQUEST['crr']) ? xssClean(trim($_REQUEST['crr'])) : 0;              // 구름저항계수 (Coefficient of Rolling Resistance)
$params['cda'] = isset($_REQUEST['cda']) ? xssClean(trim($_REQUEST['cda'])) : 0;              // 공기저항면적 (Coefficient of Drag × Area, m²)
$params['rim_height'] = isset($_REQUEST['rim_height']) ? xssClean(trim($_REQUEST['rim_height'])) : 0;  // 휠 림 높이 (mm)

// ── 바이크 키트 상세 설정 ──
//for bike kit
$params['tire_product'] = isset($_REQUEST['tire_product']) ? xssClean(trim($_REQUEST['tire_product'])) : 1022;    // 타이어 제품 ID
$params['tire_width'] = isset($_REQUEST['tire_width']) ? xssClean(trim($_REQUEST['tire_width'])) : 2;              // 타이어 폭 인덱스
$params['cadence'] = isset($_REQUEST['cadence']) ? xssClean(trim($_REQUEST['cadence'])) : 90;                      // 케이던스 (rpm)
$params['rider_pose'] = isset($_REQUEST['rider_pose']) ? xssClean(trim($_REQUEST['rider_pose'])) : 2;              // 라이딩 자세 (1:업라이트, 2:노멀, 3:에어로)
$params['surface_select'] = isset($_REQUEST['surface_select']) ? xssClean(trim($_REQUEST['surface_select'])) : 2;  // 노면 상태

// ── 계산 옵션 ──
$params['grade'] = isset($_REQUEST['grade']) ? xssClean(trim($_REQUEST['grade'])) : 0.00;     // 경사도 (소수, 예: 0.05 = 5%)
$params['age'] = isset($_REQUEST['age']) ? xssClean(trim($_REQUEST['age'])) : 30;             // 나이 - 기초대사량 계산용
$params['result_select'] = isset($_REQUEST['result_select']) ? xssClean(trim($_REQUEST['result_select'])) : 'speedToPower';
// result_select 옵션:
//   - 'speedToPower'  : 속도 → 필요 파워 계산
//   - 'powerToSpeed'  : 파워 → 예상 속도 계산
//   - 'estimateCdA'   : 파워+속도로 CdA 역산
//   - 'estimatePR'    : 코스에 대한 PR(개인기록) 예측

// ── 메인 입력값 ──
$avgPower = ($_REQUEST['avg_power'] > 0) ? xssClean(trim($_REQUEST['avg_power'])) : 100;      // 평균 파워 (W)
$avgSpeed = ($_REQUEST['avg_speed'] > 0) ? xssClean(trim($_REQUEST['avg_speed'])) : 10;       // 평균 속도 (km/h)

// ── 구동계 ──
$params['drivetrain'] = isset($_REQUEST['drivetrain']) ? xssClean(trim($_REQUEST['drivetrain'])) : 'ultegra';
// drivetrain 옵션: duraAce, ultegra, 105, tiagra, sora, claris, sis (Shimano)
//                  redAxs, forceAxs, rival, apex (SRAM)
//                  superRecord, Record, Chorus, Potenza, Athena, Veloce, Centaur (Campagnolo)



if( $params['result_select'] == "speedToPower") {
	$json['user_result'] = calculate($avgPower, $avgSpeed, $params);

	$min = (($avgSpeed-10) > 0) ? ($avgSpeed-10) : 5;

	for($x = $min; $x <= ($avgSpeed+10); $x += 0.5) {
		$result = calculate(0, $x, $params);
		$json['power_table'][] = $result;
	}

} else if( $params['result_select'] == "powerToSpeed") {
	$json['user_result'] = calculate($avgPower, $avgSpeed, $params);

	$min = (($avgPower-100) > 0) ? ($avgPower-100) : 50;

	for($x = $min; $x <= ($avgPower+100); $x += 5) {
		$result = calculate($x, 0, $params);
		$json['power_table'][] = $result;
	}
} else if( $params['result_select'] == "estimateCdA") {

	$json['user_result'] = calculate($avgPower, $avgSpeed, $params);

} else if( $params['result_select'] == "estimatePR") {
	global $wpdb;


//151, 100, 57, 460, 4, 563, 34, 976, 93, 539
	$test_id = 2;
	
	if($user_id == 2) $user_id = $test_id;

	$extra_info = $wpdb->get_row($wpdb->prepare("SELECT ftp, weight, pdc_json FROM riduck_user_extrainfo WHERE user_id = %d LIMIT 1", array($user_id)));		
	$ftp = json_decode($extra_info->ftp);
	$weight = $extra_info->weight;
	$pdc_json = json_decode($extra_info->pdc_json);

	$real_curve = $pdc_json->power_all;
	$ai_curve =  $pdc_json->stereo_all; //(object)ftpToCurve($ftp, $weight);

//echo $ftp;
//print_r($real_curve);
//print_r($ai_curve);

	$json['user_result'] = calculate($ftp, 0, $params);
//	$json['user_result'] = $j_result;

//abs watts는 5 미만 시간은 그 중에서 abs 가장 작은 값   

	//PR을 예측하기 위함 
	$json['power_table'] = null;
	$json['workable_pr'] = pr_estimate($ftp, $real_curve, $params); 
	$json['ideal_pr'] = pr_estimate($ftp, $ai_curve, $params); 

} else {
	$params['gradeCalc'] = round(($params['elevation']/($params['distance']*1000)) * 100, 2);
	$json['user_result'] = $params;
}



/*
세미에어로 
에어로최적화  
CdA 차이 
0.88
*/

$json['bikeKit'] = setBikeKit($params, $user_id, false);

echo urldecode(json_encode($json));




function pr_estimate($ftp, $curve, $params) {
	if($ftp == 0) {
		return Array('time'=>0, 'power'=>0, 'e_range'=>Array(0, 0));
	}

	$temp_power_arr = null;

	$j_result = calculate($ftp, 0, $params);
	$fit_jouls = $j_result['jouls'];

	$min = (($ftp-200) > 0) ? ($ftp-200) : 100;

	for($x = $min; $x <= ($ftp+200); $x += 5) {
		$r_arr = calculate($x, 0, $params);
		$temp_power_arr[] = Array(round($r_arr['time']), round($r_arr['power']));
	}

	$min_sec = 0;
	$max_sec = 0;
	foreach($curve as $sec => $power) {
		if($fit_jouls < $sec*$power) {
			$max_sec = $sec; 
			break;
		} else {
			$min_sec = $sec;
		}
	}

	if($min_sec!=0 && $max_sec!=0) {
		$tail_power = $curve->$max_sec;
		$head_power = $curve->$min_sec;
		$slope = ($tail_power-$head_power)/($max_sec-$min_sec);
		
		$t_arr = null; 
		$p_arr = null; 

		for($i = 0; $i <= ($max_sec-$min_sec); $i+=5 ) {
			$power = $head_power + $slope*$i;
			$sec = $min_sec+$i;
			//$pr_arr[] = Array($power, transTime($sec/60));			

			foreach($temp_power_arr as $t => $arr) {
				$t = $arr[0];
				$p = $arr[1];

				if( abs($power-$p) < 5 ) {
					$t_arr[] = $t;
					$p_arr[] = $p;
				}
			}		
		}

		$t_max = max($t_arr);
		$t_min = min($t_arr);
		$t_pr = ($t_max+$t_min)/2;
		$t_e_range = ($t_max-$t_min)/2;

		$p_max = max($p_arr);
		$p_min = min($p_arr);
		$p_pr = ($p_max+$p_min)/2;
		$p_e_range = ($p_max-$p_min)/2;

		return Array(
			'time'=>$t_pr,
			'time_string'=>transTime($t_pr/60),
			'power'=>$p_pr,
			'e_range'=>Array(transTime($t_e_range/60), $p_e_range)
		);
	} else {

		return Array('time'=>0, 'power'=>0, 'e_range'=>Array(0, 0));
	}
}



/*******************************************************************************
 * calculate() - 핵심 시뮬레이션 계산 함수
 * 
 * 물리 법칙 기반으로 파워↔속도 변환, CdA 추정, PR 예측 등을 수행하는 메인 계산 엔진
 * 
 * @param float $avgPower  입력 파워 (W) - powerToSpeed, estimatePR, estimateCdA 모드에서 사용
 * @param float $avgSpeed  입력 속도 (km/h) - speedToPower, estimateCdA 모드에서 사용
 * @param array $params    시뮬레이션 파라미터 배열 (라이더/자전거/환경 정보)
 * @return array           계산 결과 (power, speed, time, CdA, calorie, fat_burn 등)
 * 
 * ─────────────────────────────────────────────────────────────────────────────
 * 사용된 물리 공식 및 출처:
 * ─────────────────────────────────────────────────────────────────────────────
 * 
 * [1] 기초대사량 (BMR) - Harris-Benedict Equation (1918)
 *     남: BMR = 66.47 + (13.7 × 체중kg) + (5 × 키cm) - (6.76 × 나이)
 *     여: BMR = 655.1 + (9.58 × 체중kg) + (1.85 × 키cm) - (4.68 × 나이)
 *     출처: Harris JA, Benedict FG. "A Biometric Study of Human Basal Metabolism"
 *           Proc Natl Acad Sci USA. 1918;4(12):370-373
 *           https://doi.org/10.1073/pnas.4.12.370
 * 
 * [2] 기초대사량 (BMR) - Mifflin-St Jeor Equation (1990) [참고용, 미사용]
 *     남: BMR = (10 × 체중kg) + (6.25 × 키cm) - (5 × 나이) + 5
 *     여: BMR = (10 × 체중kg) + (6.25 × 키cm) - (5 × 나이) - 161
 *     출처: Mifflin MD, St Jeor ST, et al. "A new predictive equation for 
 *           resting energy expenditure in healthy individuals"
 *           Am J Clin Nutr. 1990;51(2):241-247
 *           https://doi.org/10.1093/ajcn/51.2.241
 * 
 * [3] 공기밀도 공식 - ISA(International Standard Atmosphere) 기반
 *     ρ = (1.293 - 0.00426 × T) × exp(-h × 0.709 / 7000)
 *     - 1.293 kg/m³: 0°C 해수면 표준 공기밀도
 *     - 온도 보정: -0.00426 kg/m³/°C
 *     - 고도 보정: 지수 감소 모델 (scale height ≈ 7000m)
 *     출처: ISO 2533:1975 "Standard Atmosphere"
 * 
 * [4] 사이클링 파워 방정식
 *     P = v × (F_gravity + F_rolling + F_aero) / η_drivetrain
 *     - F_gravity = m × g × grade (중력 저항)
 *     - F_rolling = m × g × Crr (구름 저항)  
 *     - F_aero = 0.5 × ρ × CdA × v² (공기 저항)
 *     출처: Martin JC, et al. "Validation of a mathematical model for 
 *           road cycling power" J Appl Biomech. 1998;14(3):276-291
 * 
 * [5] Newton-Raphson Method - 속도 수렴 알고리즘
 *     비선형 방정식 f(v) = 0 의 근을 찾는 수치해석 방법
 *     v_new = v - f(v) / f'(v)
 *     출처: Numerical Recipes, Press WH et al., Cambridge University Press
 ******************************************************************************/
function calculate($avgPower, $avgSpeed, $params) {
	$powerv = $speed = $t = 0;

	$resultSelect = $params['result_select'];

	// ── 라이더 정보 추출 ──
	$gender = $params['gender']; 
	$age = $params['age']; 
	$rider_weight = $params['rider_weight']; 
	$rider_height = $params['rider_height']; 

	// ── 주행 환경 정보 추출 ──
	$distancev = $params['distance']; 
	$temperaturev = $params['temperature'];  
	$elevationv = $params['elevation'];  
	$altitude = $params['altitude'];  
	$gradev = $params['grade'];

	// ── 자전거 정보 추출 ──
	$bike_type = $params['bike_type'];
	$bike_weight = $params['bike_weight']; 	
	
	// 경사도 자동 계산: 거리와 고도차가 주어지고 grade가 0인 경우
	if(($distancev > 0 && $elevationv > 0) && $gradev == 0) {
		$gradev = $elevationv/($distancev*1000);  // 소수 형태 (예: 0.05 = 5%)
	} 

	/*
	 * ═══════════════════════════════════════════════════════════════════════
	 * 기초대사량(BMR) 계산 - Harris-Benedict Equation (1918)
	 * ═══════════════════════════════════════════════════════════════════════
	 * 
	 * 칼로리 소모량 계산의 기반이 되는 기초대사량을 산출
	 * 현재는 Harris-Benedict 공식 사용 (역사적으로 가장 널리 사용됨)
	 * 
	 * 참고: Mifflin-St Jeor 공식(1990)이 더 정확하다는 연구 결과가 있으나,
	 *       기존 시스템과의 호환성을 위해 Harris-Benedict 유지
	 * 
	 * 출처: Harris JA, Benedict FG. Proc Natl Acad Sci USA. 1918;4(12):370-373
	 *       https://doi.org/10.1073/pnas.4.12.370
	 */
	//남자 여자 표준 대사량 + 앉아있을 때 열량 해리스 베니딕트 
	if($gender == "M") {
		$default_cal = 66.47 + (13.7*$rider_weight) + (5*$rider_height) - (6.76*$age);
	} elseif($gender == "F") {
		$default_cal = 665.1 + (9.58*$rider_weight) + (1.85*$rider_height) - (4.68*$age);	
	}
	/*
	 * [참고] Mifflin-St Jeor 공식 (1990) - 더 정확한 현대 공식
	 * 출처: Am J Clin Nutr. 1990;51(2):241-247
	 *       https://doi.org/10.1093/ajcn/51.2.241
	 */
	//미플리 세인트 지어 
	//여자 = (6.25 x 키) + (10 x 체중) – (5 x 나이) – 161
	//남자 = (6.25 x 키) + (10 x 체중) – (5 x 나이) + 5

	//업힐에 따른 에어로다이나믹 

	// ── 저항 계수 ──
	$rollingRes = $params['crr'];       // 구름저항계수 (Coefficient of Rolling Resistance)
	$frontalArea = $params['cda'];      // 공기저항면적 (Drag Coefficient × Frontal Area, m²)
	$rimHeight = $params['rim_height']; // 림 높이 (mm) - 공력 휠 효과

	$headwindv = 0;  // 맞바람 속도 (m/s) - 현재 미사용, 향후 확장용

	$dt = $params['drivetrain'];  // 구동계 종류

	/*
	 * ═══════════════════════════════════════════════════════════════════════
	 * 공기밀도 계산 - ISA(International Standard Atmosphere) 기반
	 * ═══════════════════════════════════════════════════════════════════════
	 * 
	 * 공식: ρ = ρ₀ × (1 - αT) × exp(-h/H)
	 * - ρ₀ = 1.293 kg/m³ (0°C, 해수면 표준 공기밀도)
	 * - α = 0.00426 (온도 계수, 약 -0.33%/°C)
	 * - H = 7000/0.709 ≈ 9873m (scale height, 대기 스케일 높이)
	 * 
	 * 출처: ISO 2533:1975 "Standard Atmosphere"
	 */
	/* Common calculations */
	$density = (1.293 - 0.00426 * $temperaturev) * exp(-($altitude*0.709) / 7000.0);
	
	/*
	 * 총 무게(뉴턴) = 중력가속도 × (라이더 + 자전거 + 장비)
	 * - 9.798 m/s² ≈ 표준 중력가속도 (위도 45° 기준)
	 * - +1.0 kg: 헬멧, 신발, 물통 등 추가 장비 무게
	 */
	$twt = 9.798 * ($rider_weight + $bike_weight + 1.0);  // total weight in Newtons 헬멧 등 다 포함
	
	/*
	 * 총 저항력 = 중력저항 + 구름저항
	 * - 중력저항: twt × grade (경사에 의한 저항)
	 * - 구름저항: twt × Crr (타이어-노면 마찰)
	 */
	$tres = $twt * ($gradev + $rollingRes); // gravity and rolling resistance
		
	if($resultSelect == "powerToSpeed") {	
		$powerv = $avgPower;
		$transv = drivetrainEfficiency($dt, $avgPower);

		$A2 = 0.5 * $frontalArea * $density;  // full air resistance parameter
		
		$v = Newton($A2, $headwindv, $tres, $transv, $powerv) * 3.6;      // convert to km/h
		if ($v > 0.0) $t = (60.0 * $distancev) / $v;
		else $t = 0.0;  // don't want any div by zero errors

		$speed = makeDecimal2($v);
			
	} else if($resultSelect == "speedToPower") {  
		$speed = $avgSpeed;

		$A2 = 0.5 * $frontalArea * $density;  // full air resistance parameter
	
		$v = $speed / 3.6;  // converted to m/s;
		$tv = $v + $headwindv; 
		$A2Eff = ($tv > 0.0) ? $A2 : -$A2; // wind in face, must reverse effect
		$powerv100 = ($v * $tres + $v * $tv * $tv * $A2Eff); 

		$transv = drivetrainEfficiency($dt, $powerv100); // transv를 나중에 구함 
		$powerv	= $powerv100 / $transv;
			
		if ($v > 0.0) $t = (16.6667 * $distancev) / $v;  // v is m/s here, t is in minutes
		else $t = 0.0;  // don't want any div by zero errors
	} else if($resultSelect == "estimatePR") {	
		$powerv = $avgPower;
		$transv = drivetrainEfficiency($dt, $avgPower);

		$A2 = 0.5 * $frontalArea * $density;  
		
		$v = Newton($A2, $headwindv, $tres, $transv, $powerv) * 3.6;      
		if ($v > 0.0) $t = (60.0 * $distancev) / $v;
		else $t = 0.0;  

		$speed = makeDecimal2($v);
			
	} else if($resultSelect == "estimateCdA") {
		$powerv = $avgPower;
		$speed = $avgSpeed;
		$transv = drivetrainEfficiency($dt, $avgPower);

		$v = $speed / 3.6;  // converted to m/s;
		$tv = $v + $headwindv; 

		$A2Eff = (($powerv * $transv) - ($v * $tres)) / ($v * $tv * $tv);
		$A2 = ($A2Eff > 0) ? $A2Eff : -$A2Eff;
		
		$frontalArea = $A2 * 2.0 / $density;
	
		if ($v > 0.0) $t = (16.6667 * $distancev) / $v;  // v is m/s here, t is in minutes
		else $t = 0.0;  // don't want any div by zero errors
	}


	/* Common calculations */
	//	$c = $t * 60.0 * $powerv / 0.25 / 1000.0; // kilowatt-seconds, aka kilojoules. t is converted to seconds from minutes, 25% conversion efficiency

	/*
kg, m, m/s
CdA=((((파워*동력전달효율)-(속도*9.798*(자전거무게+체중)*((획득고도/이동거리)+CRR)))/(속도*속도*속도))*2)/(1.293-0.00426*섭씨온도)*exp(-1*(평균고도*0.709)/7000.0);
	*/

//림에 대한 것은 최종 와트에서 빼야 함 
//x=speed 
//y=절감와트 
//y = (1.8x-36) -> 이걸 60등분하면 된다. 35mm 6분의1, 50mm 12분의 5, 65mm 3분의2, 80mm 11/12퍼로 가자   

	$jouls = $t * 60 * $powerv;
	$kj = $t * $powerv * 0.24;  // simplified
	$cal = ($kj * 0.239) + ($default_cal * $t/1440 * 1.55);	//자전거운동에너지 + 기초대사량 또는 1.2 1.375

	$fb = ($cal/3500)*0.45;		// 1pound 3500cal to kg
	$wkg = $powerv / $rider_weight; 

	$result['resultSelect'] = $resultSelect;
	$result['power'] = round($powerv);
	$result['wkg'] = makeDecimal2($wkg);
	$result['time_string'] = transTime($t);
	$result['time'] = $t*60;
	$result['distance'] = makeDecimal2($distancev);
	$result['speed'] = makeDecimal2($speed);
	$result['CdA'] = makeDecimal4($frontalArea);
	$result['jouls'] = round($jouls);
	$result['calorie'] = makeDecimal4($cal);
	$result['fat_burn'] = makeDecimal4($fb);

	$result['gradeCalc'] = round($gradev*100, 2);

	return $result;
}




//($params, $json, $user, $token, $updateConfig);

function setBikeKit($params, $user_id, $option) {
	global $wpdb;

	$bikeKit = null;	

	$bikeKit['gender'] = $gender = $params['gender'];
	$bikeKit['rider_height'] = $rider_height = makeDecimal2($params['rider_height']);
	$bikeKit['rider_weight'] = $rider_weight = makeDecimal2($params['rider_weight']);
	$bikeKit['bike_type'] = $bike_type = $params['bike_type'];
	$bikeKit['bike_weight'] = $bike_weight = makeDecimal2($params['bike_weight']);
	$bikeKit['tire_product'] = $tire_product = $params['tire_product'];
	$bikeKit['drivetrain'] = $drivetrain = $params['drivetrain'];
	$bikeKit['tire_width'] = $tire_width = $params['tire_width'];
	$bikeKit['rim_height'] = $rim_height = $params['rim_height'];
	$bikeKit['cadence'] = $cadence = $params['cadence'];
	$bikeKit['rider_pose'] = $rider_pose = $params['rider_pose'];
	$bikeKit['crr'] = $crr = makeDecimal6($params['crr']);
	$bikeKit['cda'] = $cda = makeDecimal6($params['cda']);
	$bikeKit['surface_select'] = $surface_select = $params['surface_select'];

	$bikeKit_json = urldecode(json_encode($bikeKit));

	$wpdb->query($wpdb->prepare("UPDATE riduck_user_extrainfo SET bikeKit_json = %s WHERE user_id = %d LIMIT 1", array($bikeKit_json, $user_id)));

	$usql = "UPDATE riduck_bike_kit SET 
				gender = '{$gender}',
				rider_height = '{$rider_height}',
				rider_weight = '{$rider_weight}',
				bike_type = '{$bike_type}',
				bike_weight = '{$bike_weight}',
				tire_product = '{$tire_product}',
				drivetrain = '{$drivetrain}',
				tire_width = '{$tire_width}',
				rim_height = '{$rim_height}',
				cadence = '{$cadence}',
				rider_pose = '{$rider_pose}',
				crr = '{$crr}',
				cda = '{$cda}',
				surface_select = '{$surface_select}',
				updated_at = '".date("YmdHis")."' 
			WHERE user_id = '".$user_id."' LIMIT 1"; 

	$result = $wpdb->query($usql);

	if(!$result) {
		$isql = "INSERT INTO riduck_bike_kit SET 
			user_id = '".$user_id."',
			gender = '{$gender}',
			rider_height = '{$rider_height}',
			rider_weight = '{$rider_weight}',
			bike_type = '{$bike_type}',
			bike_weight = '{$bike_weight}',
			tire_product = '{$tire_product}',
			drivetrain = '{$drivetrain}',
			tire_width = '{$tire_width}',
			rim_height = '{$rim_height}',
			cadence = '{$cadence}',
			rider_pose = '{$rider_pose}',
			crr = '{$crr}',
			cda = '{$cda}',
			surface_select = '{$surface_select}',
			updated_at = '".date("YmdHis")."'"; 

		$result = $wpdb->query($isql);		
	}

	$rtv = $params;	

	return $rtv; 
}





function makeDecimal2 ($v) {
	$x = (float)$v;
	return round($v,2);
}

function makeDecimal4 ($v) {
	$x = (float)$v;
	return round($v,4);
}

function makeDecimal6 ($v) {
	$x = (float)$v;
	return round($v,6);
}

function makeDecimal0 ($v) {
	return round($v,0);
}

function transTime($v) {
	$dec = $v - (int)$v;
	$m = (int)$v;

	if($m < 1) { 
		$ss = round($dec*60, 1); 
		return $ss."초";
	} else if($m > 60) {
		$h = (int)($m / 60);
		$mm = $m % 60;	
		$ss = round($dec*60); 

		return $h."시간 ".$mm."분 ".$ss."초";
	} else {
		$ss = round($dec*60); 
		return $m."분 ".$ss."초";
	}
}

function Newton($aero, $hw, $tr, $tran, $p) {        /* Newton's method */
	$vel = 20;       // Initial guess
	$MAX = 10;       // maximum iterations
	$TOL = 0.05;     // tolerance
	for ($i=1; $i < $MAX; $i++) {
		$tv = $vel + $hw;
		$aeroEff = ($tv > 0.0) ? $aero : -$aero; // wind in face, must reverse effect
		$f = $vel * ($aeroEff * $tv * $tv + $tr) - $tran * $p; // the function
		$fp = $aeroEff * (3.0 * $vel + $hw) * $tv + $tr;     // the derivative
		$vNew = $vel - $f / $fp;
		if (abs($vNew - $vel) < $TOL) return $vNew;  // success
		$vel = $vNew;
	}

	return 0.0;  // failed to converge
}

function setMode($mode) { // called when velocity is entered
	$calcMode = $mode;
}


function drivetrainEfficiency($dt, $powerv) {

	switch($dt) {
	    case "duraAce":
			$efficiency = 0.963; break;
		case "ultegra":
			$efficiency = 0.962; break;
		case "105":
			$efficiency = 0.961; break;
		case "tiagra":
			$efficiency = 0.960; break;
		case "sora":
			$efficiency = 0.958; break;
		case "claris":
			$efficiency = 0.956; break;
		case "sis":
			$efficiency = 0.940; break;
	
		case "redAxs":
			$efficiency = 0.965; break;
		case "forceAxs":
			$efficiency = 0.962; break;
		case "rival":
			$efficiency = 0.961; break;
		case "apex":
			$efficiency = 0.960; break;
		
		case "superRecord":
			$efficiency = 0.963; break;
		case "Record":
			$efficiency = 0.962; break;
		case "Chorus":
			$efficiency = 0.961; break;
		case "Potenza":
			$efficiency = 0.960; break;
		case "Athena":
			$efficiency = 0.960; break;
		case "Veloce":
			$efficiency = 0.958; break;
		case "Centaur":
			$efficiency = 0.958; break;

		case "kForce":
			$efficiency = 0.962; break;
		
		default:
			$efficiency = 0.962; break;
	}
	
	if($powerv >= 400) $pm = 400;
	elseif($powerv <= 50) $pm = 50;
	else $pm = $powerv;

	$r = 2.1246*log($pm) - 11.5;
	$rtv = ($r + $efficiency*100)/100;

	return $rtv;
}


function ftpToCurve($ftp, $weight) {
	global $power_curve_model;

	$search_time_min = 1;
	$search_time_max = 7200;

	$seconds = 2700;

	$result_array = null;
	$my_wkg = $ftp/$weight;

	//1시간 이후는 20/60의 시간거듭제곱 

	$maxWkg = $power_curve_model['maxWkg'];
	$minWkg = $power_curve_model['minWkg'];

	foreach ($minWkg as $key => $wkg) {
		if($key > $seconds) {
			$search_time_max = $key;
			break;
		} else {		
			$search_time_min = $key;
		}
	};

	$time_rate = ($seconds - $search_time_min)/($search_time_max - $search_time_min);			
	$search_max_wkg = $maxWkg[$search_time_min] + ($maxWkg[$search_time_max] - $maxWkg[$search_time_min]) * $time_rate;
	$search_min_wkg = $minWkg[$search_time_min] + ($minWkg[$search_time_max] - $minWkg[$search_time_min]) * $time_rate;
		
	$wkg_rate = ($my_wkg - $search_min_wkg)/($search_max_wkg - $search_min_wkg);

	$index = 0;

	foreach ($minWkg as $key => $wkg) {
		$ap = $minWkg[$key] + ($maxWkg[$key]-$minWkg[$key])*$wkg_rate;

		$result_array[$key] = round($ap*$weight, 1);
	}

	return $result_array;
}






```
